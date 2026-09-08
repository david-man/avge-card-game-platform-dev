from __future__ import annotations

from typing import Any, Callable, cast
from card_game.server.server_types import JsonObject, CommandPayload

from ..models.server_models import ClientSession, MultiplayerTransportState, PendingCommandAck, PlayerSlot
from ..protocol.command_codec import command_action, to_wire_command


def enqueue_bridge_commands(
    commands: list[JsonObject],
    source_slot: str | None,
    *,
    next_command_id: int,
    winner_announced: bool,
    winner_main_menu_ack_slots: set[PlayerSlot],
    pending_command_acks: list[PendingCommandAck],
    pending_command_ack_factory: Callable[..., PendingCommandAck],
    classify_required_ack_slots: Callable[[str, str | None], set[PlayerSlot]],
    mark_room_finished_once: Callable[[str], None],
    transport_lock: Any,
    registration_condition: Any,
    emit_ready_commands_to_connected_clients: Callable[[], None],
    emit_pending_peer_ack_status_to_connected_clients: Callable[[], None],
) -> tuple[int, bool, set[PlayerSlot]]:
    expanded_commands: list[JsonObject] = []
    for command in commands:
        if not isinstance(command, dict):
            continue

        raw_command = command.get('command')
        if not isinstance(raw_command, str):
            continue

        command_text = raw_command.strip()
        response_payload: JsonObject | None = None
        raw_payload = command.get('response_payload')
        if isinstance(raw_payload, dict):
            response_payload = raw_payload

        if not isinstance(command_text, str) or not command_text:
            continue

        wire_command = to_wire_command(command_text)
        if not wire_command:
            continue

        expanded_commands.append({
            'command': wire_command,
            'response_payload': response_payload,
        })

    if any(
        isinstance(entry.get('command'), str)
        and command_action(str(entry['command'])) == 'winner'
        for entry in expanded_commands
    ):
        winner_announced = True
        winner_main_menu_ack_slots = set()
        mark_room_finished_once('winner_declared')

    for entry in expanded_commands:
        command = str(entry.get('command', '')).strip()
        response_payload = entry.get('response_payload') if isinstance(entry.get('response_payload'), dict) else None
        pending_command_acks.append(
            pending_command_ack_factory(
                command_id=next_command_id,
                command=command,
                required_slots=classify_required_ack_slots(command, source_slot),
                response_payload=response_payload,
            )
        )
        next_command_id += 1

    if expanded_commands:
        with transport_lock:
            registration_condition.notify_all()
        emit_ready_commands_to_connected_clients()
        emit_pending_peer_ack_status_to_connected_clients()

    return next_command_id, winner_announced, winner_main_menu_ack_slots


def emit_ready_commands_to_connected_clients(
    *,
    socketio: Any,
    transport_lock: Any,
    transport_state: MultiplayerTransportState,
    commands_ready_for_slot: Callable[[str | None, bool, ClientSession | None], list[JsonObject]],
    protocol_packets_emit_payload_for_slot: Callable[[str | None, list[JsonObject]], JsonObject],
    log_protocol_send: Callable[[list[JsonObject], str | None], None],
) -> None:
    if socketio is None:
        return

    deliveries: list[tuple[PlayerSlot, str, list[JsonObject]]] = []
    with transport_lock:
        for slot_name in ('p1', 'p2'):
            slot = cast(PlayerSlot, slot_name)
            sid_for_slot = transport_state.sid_by_slot[slot]
            if sid_for_slot is None:
                continue
            session = transport_state.session_by_sid.get(sid_for_slot)
            if session is None:
                continue
            packets = commands_ready_for_slot(slot, is_response=True, session=session)
            if not packets:
                continue
            deliveries.append((slot, sid_for_slot, packets))

    for slot, sid_for_slot, packets in deliveries:
        socketio.emit('protocol_packets', protocol_packets_emit_payload_for_slot(slot, packets), to=sid_for_slot)
        log_protocol_send(packets, slot)


def emit_pending_peer_ack_status_to_connected_clients(
    *,
    socketio: Any,
    transport_lock: Any,
    transport_state: MultiplayerTransportState,
    protocol_packets_emit_payload_for_slot: Callable[[str | None, list[JsonObject]], JsonObject],
    log_protocol_send: Callable[[list[JsonObject], str | None], None],
) -> None:
    if socketio is None:
        return

    deliveries: list[tuple[PlayerSlot, str, JsonObject]] = []
    with transport_lock:
        for slot_name in ('p1', 'p2'):
            slot = cast(PlayerSlot, slot_name)
            sid_for_slot = transport_state.sid_by_slot[slot]
            if sid_for_slot is None:
                continue

            deliveries.append((
                slot,
                sid_for_slot,
                protocol_packets_emit_payload_for_slot(slot, []),
            ))

    for slot, sid_for_slot, payload in deliveries:
        socketio.emit('protocol_packets', payload, to=sid_for_slot)
        log_protocol_send([], slot)
