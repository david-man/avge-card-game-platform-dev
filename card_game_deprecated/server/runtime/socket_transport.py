from __future__ import annotations

from typing import Any
from card_game.server.server_types import JsonObject, CommandPayload
from typing import Callable
from typing import cast

from ..models.server_models import ClientSession, MultiplayerTransportState, PlayerSlot


def emit_server_connected(*, emit_fn: Callable[[str, JsonObject], None] | None) -> None:
    if emit_fn is None:
        return
    emit_fn('server_status', {
        'ok': True,
        'transport': 'socketio',
        'message': 'connected',
    })


def register_client_or_play(
    payload: Any,
    *,
    sid: str,
    transport_lock: Any,
    transport_state: MultiplayerTransportState,
    socketio: Any,
    emit_fn: Callable[[str, JsonObject], None] | None,
    process_protocol_packet: Callable[[JsonObject, str | None], tuple[JsonObject, int]],
    drain_pending_packets_for_session: Callable[[ClientSession], list[JsonObject]],
    protocol_packets_emit_payload_for_slot: Callable[[str | None, list[JsonObject]], JsonObject],
    log_protocol_send: Callable[[list[JsonObject], str | None], None],
) -> None:
    if emit_fn is None:
        return

    data = payload if isinstance(payload, dict) else {}

    requested_slot_raw = data.get('slot')
    requested_slot = requested_slot_raw.strip() if isinstance(requested_slot_raw, str) and requested_slot_raw.strip() else None

    reconnect_token_raw = data.get('reconnect_token')
    reconnect_token = reconnect_token_raw.strip() if isinstance(reconnect_token_raw, str) and reconnect_token_raw.strip() else None

    router_session_id_raw = data.get('session_id')
    router_session_id = router_session_id_raw.strip() if isinstance(router_session_id_raw, str) else None

    register_body: JsonObject = {}
    if requested_slot is not None:
        register_body['requested_slot'] = requested_slot
    if router_session_id is not None and router_session_id.strip():
        register_body['session_id'] = router_session_id

    register_packet: JsonObject = {
        'ACK': 0,
        'PacketType': 'register_client',
        'Body': register_body,
        'client_id': sid,
    }
    if reconnect_token is not None:
        register_packet['reconnect_token'] = reconnect_token

    response, status = process_protocol_packet(register_packet, None)
    if status != 200 or response.get('ok') is not True:
        emit_fn('registration_error', {
            'ok': False,
            'error': response.get('error') if isinstance(response.get('error'), str) else 'Both player slots are occupied.',
        })
        return

    with transport_lock:
        assigned_slot = transport_state.slot_for_sid(sid)
        session = transport_state.session_by_sid.get(sid)
        peer_sessions: list[tuple[str, PlayerSlot, ClientSession]] = []
        for slot_name in ('p1', 'p2'):
            slot = cast(PlayerSlot, slot_name)
            peer_sid = transport_state.sid_by_slot[slot]
            if peer_sid is None or peer_sid == sid:
                continue
            peer_session = transport_state.session_by_sid.get(peer_sid)
            if peer_session is None:
                continue
            peer_sessions.append((peer_sid, slot, peer_session))

    response_slot = response.get('client_slot')
    if isinstance(response_slot, str) and response_slot in {'p1', 'p2'}:
        assigned_slot = cast(PlayerSlot, response_slot)

    response_reconnect_token = response.get('reconnect_token')
    both_connected = response.get('both_players_connected') is True
    waiting_for_init = response.get('waiting_for_init') is True
    pending_replay_count = len(session.pending_commands) if session is not None else 0

    emit_fn('registration_ok', {
        'ok': True,
        'slot': assigned_slot,
        'reconnect_token': response_reconnect_token if isinstance(response_reconnect_token, str) else None,
        'both_players_connected': both_connected,
        'waiting_for_init': waiting_for_init,
        'pending_replay_count': pending_replay_count,
    })

    register_packets_raw = response.get('packets')
    register_packets = register_packets_raw if isinstance(register_packets_raw, list) else []

    if socketio is not None and register_packets:
        socketio.emit(
            'protocol_packets',
            protocol_packets_emit_payload_for_slot(assigned_slot, register_packets),
            to=sid,
        )
        log_protocol_send(register_packets, assigned_slot)

    if both_connected and socketio is not None and assigned_slot in {'p1', 'p2'}:
        for peer_sid, peer_slot, peer_session in peer_sessions:
            peer_packets = drain_pending_packets_for_session(peer_session)
            if peer_packets:
                socketio.emit(
                    'protocol_packets',
                    protocol_packets_emit_payload_for_slot(peer_slot, peer_packets),
                    to=peer_sid,
                )
                log_protocol_send(peer_packets, peer_slot)

        for peer_sid, _, _ in peer_sessions:
            socketio.emit('opponent_reconnected', {
                'slot': assigned_slot,
                'both_players_connected': True,
            }, to=peer_sid)


def handle_protocol_socket_event(
    payload: Any,
    *,
    sid: str,
    packet_type: str,
    transport_lock: Any,
    transport_state: MultiplayerTransportState,
    process_protocol_packet: Callable[[JsonObject, str | None], tuple[JsonObject, int]],
    protocol_packets_emit_payload_for_slot: Callable[[str | None, list[JsonObject]], JsonObject],
    emit_fn: Callable[[str, JsonObject], None] | None,
) -> None:
    if emit_fn is None:
        return

    data = payload if isinstance(payload, dict) else {}
    with transport_lock:
        client_slot = transport_state.slot_for_sid(sid)

    raw_body = data.get('Body')
    body = raw_body if isinstance(raw_body, dict) else {}

    packet = {
        'ACK': data.get('ACK'),
        'PacketType': packet_type,
        'Body': body,
        'client_id': sid,
    }
    response, status = process_protocol_packet(packet, client_slot)
    if status != 200:
        emit_fn('protocol_error', {
            **response,
            'packet_type': packet_type,
            'status': status,
        })
        return

    packets = response.get('packets', [])
    emit_fn(
        'protocol_packets',
        protocol_packets_emit_payload_for_slot(client_slot, packets if isinstance(packets, list) else []),
    )


def handle_client_unloading(
    *,
    sid: str,
    handle_transport_sid_disconnect: Callable[[str], None],
    disconnect_fn: Callable[..., None] | None,
) -> None:
    handle_transport_sid_disconnect(sid)
    if disconnect_fn is not None:
        try:
            disconnect_fn(sid=sid)
        except Exception:
            pass


def handle_disconnect(*, sid: str, handle_transport_sid_disconnect: Callable[[str], None]) -> None:
    handle_transport_sid_disconnect(sid)
