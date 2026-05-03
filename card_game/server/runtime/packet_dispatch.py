from __future__ import annotations

from typing import Any, Callable, cast
from card_game.server.server_types import JsonObject, CommandPayload

from ..models.server_models import ClientSession, MultiplayerTransportState, PendingCommandAck, PlayerSlot


def blocked_pending_command_for_slot(
    source_slot: str | None,
    *,
    pending_command_acks: list[PendingCommandAck],
    normalize_client_slot: Callable[[Any], str | None],
) -> PendingCommandAck | None:
    normalized_slot = normalize_client_slot(source_slot)
    if normalized_slot not in {'p1', 'p2'}:
        return None

    if len(pending_command_acks) == 0:
        return None

    head = pending_command_acks[0]
    awaiting_slots = head.required_slots.difference(head.acked_slots)
    if len(awaiting_slots) == 0:
        return None

    slot = cast(PlayerSlot, normalized_slot)
    if slot in awaiting_slots:
        return None

    return head


def effective_protocol_slot(
    source_slot: str | None,
    response: JsonObject | None,
    *,
    normalize_client_slot: Callable[[Any], str | None],
) -> PlayerSlot | None:
    response_slot = None
    if isinstance(response, dict):
        response_slot = normalize_client_slot(response.get('client_slot'))

    if response_slot in {'p1', 'p2'}:
        return cast(PlayerSlot, response_slot)

    normalized_source = normalize_client_slot(source_slot)
    if normalized_source in {'p1', 'p2'}:
        return cast(PlayerSlot, normalized_source)

    return None


def augment_protocol_response_with_pending_peer_ack(
    response: JsonObject,
    source_slot: str | None,
    *,
    effective_protocol_slot: Callable[[str | None, JsonObject | None], PlayerSlot | None],
    blocked_pending_command_for_slot: Callable[[str | None], PendingCommandAck | None],
) -> JsonObject:
    enriched = dict(response)
    slot = effective_protocol_slot(source_slot, response)
    blocked_pending_command = blocked_pending_command_for_slot(slot)

    enriched['blocked_pending_peer_ack'] = blocked_pending_command is not None
    if blocked_pending_command is not None and not isinstance(enriched.get('blocked_command'), str):
        enriched['blocked_command'] = blocked_pending_command.command

    return enriched


def protocol_packets_emit_payload_for_slot(
    slot: str | None,
    packets: list[JsonObject],
    *,
    blocked_pending_command_for_slot: Callable[[str | None], PendingCommandAck | None],
) -> JsonObject:
    blocked_pending_command = blocked_pending_command_for_slot(slot)
    payload: JsonObject = {
        'packets': packets,
        'blocked_pending_peer_ack': blocked_pending_command is not None,
    }

    if slot in {'p1', 'p2'}:
        payload['client_slot'] = slot

    if blocked_pending_command is not None:
        payload['blocked_command'] = blocked_pending_command.command

    return payload


def issue_environment_resync_packet_for_source(
    source_slot: str | None,
    session_for_client: ClientSession | None,
    *,
    environment_body_for_client: Callable[[str | None], JsonObject],
    issue_backend_packet: Callable[[str, JsonObject, bool], JsonObject],
    issue_backend_packet_for_session: Callable[[ClientSession, str, JsonObject, bool], JsonObject],
) -> JsonObject:
    body = environment_body_for_client(source_slot)
    if session_for_client is not None:
        return issue_backend_packet_for_session(
            session_for_client,
            'environment',
            body,
            is_response=True,
        )

    return issue_backend_packet('environment', body, is_response=True)


def emit_pending_packets_to_connected_clients(
    *,
    socketio: Any,
    transport_lock: Any,
    transport_state: MultiplayerTransportState,
    drain_pending_packets_for_session: Callable[[ClientSession], list[JsonObject]],
    protocol_packets_emit_payload_for_slot: Callable[[str | None, list[JsonObject]], JsonObject],
    log_protocol_send: Callable[[list[JsonObject], str | None], None],
    exclude_slots: set[PlayerSlot] | None = None,
) -> None:
    if socketio is None:
        return

    excluded = exclude_slots if isinstance(exclude_slots, set) else set()
    deliveries: list[tuple[PlayerSlot, str, list[JsonObject]]] = []
    with transport_lock:
        for slot_name in ('p1', 'p2'):
            slot = cast(PlayerSlot, slot_name)
            if slot in excluded:
                continue
            sid_for_slot = transport_state.sid_by_slot[slot]
            if sid_for_slot is None:
                continue
            session = transport_state.session_by_sid.get(sid_for_slot)
            if session is None or not session.pending_packets:
                continue
            packets = drain_pending_packets_for_session(session)
            if not packets:
                continue
            deliveries.append((slot, sid_for_slot, packets))

    for slot, sid_for_slot, packets in deliveries:
        socketio.emit('protocol_packets', protocol_packets_emit_payload_for_slot(slot, packets), to=sid_for_slot)
        log_protocol_send(packets, slot)
