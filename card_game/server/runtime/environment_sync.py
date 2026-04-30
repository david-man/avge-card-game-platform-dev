from __future__ import annotations

from typing import Any, Callable, cast
from card_game.server.server_types import JsonObject, CommandPayload

from ..models.server_models import ClientSession, MultiplayerTransportState, PlayerSlot


def environment_body_for_client(
    client_slot: str | None,
    *,
    current_environment_body: Callable[[], JsonObject],
    normalize_client_slot: Callable[[Any], str | None],
) -> JsonObject:
    body = current_environment_body()
    normalized = normalize_client_slot(client_slot)
    body['playerView'] = normalized if normalized in {'p1', 'p2'} else 'spectator'
    return body


def enqueue_environment_for_connected_clients(
    *,
    force: bool,
    transport_state: MultiplayerTransportState,
    remove_pending_packets_by_type: Callable[[ClientSession, str], None],
    build_packet_blueprint: Callable[[str, JsonObject, bool], JsonObject],
    environment_body_for_slot: Callable[[PlayerSlot], JsonObject],
) -> None:
    slots_needing_environment: list[PlayerSlot] = []
    for slot_name in ('p1', 'p2'):
        slot = cast(PlayerSlot, slot_name)
        sid_for_slot = transport_state.sid_by_slot[slot]
        if sid_for_slot is None:
            continue
        session = transport_state.session_by_sid.get(sid_for_slot)
        if session is None:
            continue
        if session.environment_initialized and not force:
            continue
        already_has_environment = any(
            isinstance(packet, dict) and packet.get('PacketType') == 'environment'
            for packet in session.pending_packets
        )
        if force or not already_has_environment:
            slots_needing_environment.append(slot)

    if not slots_needing_environment:
        return

    for slot in slots_needing_environment:
        sid_for_slot = transport_state.sid_by_slot[slot]
        if sid_for_slot is None:
            continue
        session = transport_state.session_by_sid.get(sid_for_slot)
        if session is None:
            continue
        if force:
            remove_pending_packets_by_type(session, 'environment')
        session.pending_packets.append(
            build_packet_blueprint(
                'environment',
                environment_body_for_slot(slot),
                is_response=True,
            )
        )
