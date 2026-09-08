from __future__ import annotations

from threading import Condition, RLock
from typing import Any, Callable, Literal, cast
from card_game.server.server_types import JsonObject, CommandPayload

from ..models.server_models import ClientSession, PendingCommandAck, PlayerSlot, MultiplayerTransportState
from .command_codec import command_action, split_command

BackendCommandResponseCategory = Literal[
    'replay_command',
    'query_input',
    'query_notify',
    'winner',
    'lock_state',
    'phase_update',
    'other',
]


def classify_command_response_category(command: str) -> BackendCommandResponseCategory:
    parts = split_command(command)
    if not parts:
        return 'other'

    action = parts[0].lower()
    if action == 'input':
        return 'query_input'

    if action in {'notify', 'reveal', 'sound'}:
        return 'query_notify'

    if action == 'winner':
        return 'winner'

    if action in {'lock-input', 'lock_input', 'unlock-input', 'unlock_input'}:
        return 'lock_state'

    if action == 'phase':
        return 'phase_update'

    return 'replay_command'


def normalize_target_slot(raw_target: str | None) -> PlayerSlot | None:
    if not isinstance(raw_target, str):
        return None
    normalized = raw_target.strip().lower()
    if normalized in {'player-1', 'p1', 'player1'}:
        return 'p1'
    if normalized in {'player-2', 'p2', 'player2'}:
        return 'p2'
    return None


def classify_required_ack_slots(
    command: str,
    source_slot: str | None,
    transport_state: MultiplayerTransportState,
    normalize_client_slot: Callable[[Any], str | None],
) -> set[PlayerSlot]:
    parts = split_command(command)
    if not parts:
        return set()

    action = parts[0].lower()
    targeted_slot: PlayerSlot | None = None

    connected_slots: set[PlayerSlot] = {
        cast(PlayerSlot, slot)
        for slot in ('p1', 'p2')
        if transport_state.sid_by_slot[cast(PlayerSlot, slot)] is not None
    }

    # Query-notification commands (notify/reveal/sound) are visual state gates
    # for both clients. Require ACK from all connected slots before advancing
    # to the next queued command, even when the command target is single-player.
    if action in {'notify', 'reveal', 'sound'}:
        return connected_slots if connected_slots else {'p1', 'p2'}

    if action in {'lock-input', 'lock_input', 'unlock-input', 'unlock_input'} and len(parts) >= 2:
        targeted_slot = normalize_target_slot(parts[1])
        if targeted_slot is not None:
            return {targeted_slot}

    if action == 'input' and len(parts) >= 3:
        targeted_slot = normalize_target_slot(parts[2])

    if targeted_slot is not None:
        return {targeted_slot}

    if connected_slots:
        return connected_slots

    normalized_source = normalize_client_slot(source_slot)
    if normalized_source in {'p1', 'p2'}:
        return {cast(PlayerSlot, normalized_source)}

    return {'p1', 'p2'}


def build_command_packet(
    pending: PendingCommandAck,
    is_response: bool,
    session: ClientSession | None,
    issue_backend_packet: Callable[[str, JsonObject, bool], JsonObject],
    issue_backend_packet_for_session: Callable[[ClientSession, str, JsonObject, bool], JsonObject],
) -> JsonObject:
    body = {
        'command': pending.command,
        'command_id': pending.command_id,
        'target_slots': sorted(pending.required_slots),
        'response_category': classify_command_response_category(pending.command),
    }
    if isinstance(pending.response_payload, dict):
        body['response_payload'] = pending.response_payload
    if session is not None:
        return issue_backend_packet_for_session(session, 'command', body, is_response)
    return issue_backend_packet('command', body, is_response)


def commands_ready_for_slot(
    slot: str | None,
    is_response: bool,
    session: ClientSession | None,
    pending_command_acks: list[PendingCommandAck],
    normalize_client_slot: Callable[[Any], str | None],
    issue_backend_packet: Callable[[str, JsonObject, bool], JsonObject],
    issue_backend_packet_for_session: Callable[[ClientSession, str, JsonObject, bool], JsonObject],
) -> list[JsonObject]:
    packets: list[JsonObject] = []
    if not pending_command_acks:
        return packets

    head = pending_command_acks[0]
    normalized_slot = normalize_client_slot(slot)
    is_notify_command = command_action(head.command) == 'notify'

    if normalized_slot is None:
        packets.append(
            build_command_packet(
                head,
                is_response,
                session,
                issue_backend_packet,
                issue_backend_packet_for_session,
            )
        )
        return packets

    recipient = cast(PlayerSlot, normalized_slot)
    if recipient not in head.required_slots:
        if not is_notify_command:
            return packets
    if recipient in head.delivered_slots:
        return packets

    head.delivered_slots.add(recipient)
    packets.append(
        build_command_packet(
            head,
            is_response,
            session,
            issue_backend_packet,
            issue_backend_packet_for_session,
        )
    )
    return packets


def acknowledge_head_command(
    command: str | None,
    source_slot: str | None,
    pending_command_acks: list[PendingCommandAck],
    normalize_client_slot: Callable[[Any], str | None],
    registration_condition: Condition,
    transport_lock: RLock,
    command_id: int | None = None,
) -> tuple[bool, str | None]:
    if not pending_command_acks:
        return False, None

    head = pending_command_acks[0]
    _ = command
    has_command_id = isinstance(command_id, int) and not isinstance(command_id, bool)
    if not has_command_id:
        return False, None

    if head.command_id != command_id:
        return False, None

    normalized_slot = normalize_client_slot(source_slot)

    if not head.required_slots:
        pending_command_acks.pop(0)
        return True, head.command

    if normalized_slot not in {'p1', 'p2'}:
        return False, None

    slot = cast(PlayerSlot, normalized_slot)
    if slot not in head.required_slots:
        return False, None

    head.acked_slots.add(slot)
    if head.required_slots.issubset(head.acked_slots):
        pending_command_acks.pop(0)
        with transport_lock:
            registration_condition.notify_all()
        return True, head.command

    return False, None


def pending_commands_for_slot(slot: PlayerSlot, pending_command_acks: list[PendingCommandAck]) -> list[str]:
    return [
        pending.command
        for pending in pending_command_acks
        if slot in pending.required_slots and slot not in pending.acked_slots
    ]


def reset_delivery_state_for_slot(slot: PlayerSlot, pending_command_acks: list[PendingCommandAck]) -> None:
    for pending in pending_command_acks:
        if slot in pending.required_slots and slot not in pending.acked_slots:
            pending.delivered_slots.discard(slot)
