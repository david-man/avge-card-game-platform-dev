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
    expected_p1_session_id: str,
    expected_p2_session_id: str,
    room_stage: str,
    socketio: Any,
    emit_fn: Callable[[str, JsonObject], None] | None,
    expected_slot_for_router_session: Callable[[str | None], PlayerSlot | None],
    recover_reconnect_token_for_expected_slot: Callable[[PlayerSlot | None, str | None], str | None],
    cancel_disconnect_forfeit_timer_locked: Callable[[PlayerSlot], None],
    mark_player_join_seen_locked: Callable[[], None],
    enqueue_environment_for_connected_clients: Callable[..., None],
    enqueue_init_state_for_connected_clients: Callable[..., None],
    registration_condition: Any,
    short_session_id: Callable[[str | None], str],
    drain_pending_packets_for_session: Callable[[ClientSession], list[JsonObject]],
    protocol_packets_emit_payload_for_slot: Callable[[str | None, list[JsonObject]], JsonObject],
    log_protocol_send: Callable[[list[JsonObject], str | None], None],
) -> None:
    data = payload if isinstance(payload, dict) else {}
    requested_slot = data.get('slot')
    reconnect_token = data.get('reconnect_token')
    router_session_id_raw = data.get('session_id')
    router_session_id = router_session_id_raw.strip() if isinstance(router_session_id_raw, str) else None
    expected_slot = expected_slot_for_router_session(router_session_id)
    if expected_slot is not None:
        requested_slot = expected_slot

    with transport_lock:
        recovered_reconnect_token = recover_reconnect_token_for_expected_slot(
            expected_slot,
            reconnect_token if isinstance(reconnect_token, str) else None,
        )
        session = transport_state.assign_slot(
            sid=sid,
            requested_slot=requested_slot if isinstance(requested_slot, str) else None,
            reconnect_token=recovered_reconnect_token,
        )

        if session is None:
            if emit_fn is not None:
                emit_fn('registration_error', {
                    'ok': False,
                    'error': 'Both player slots are occupied.',
                })
            return

        cancel_disconnect_forfeit_timer_locked(session.slot)
        mark_player_join_seen_locked()

        both_connected = transport_state.both_players_connected()

        # Always queue environment/init state for connected clients so a
        # lone reconnect lands back in-game view immediately.
        enqueue_environment_for_connected_clients()
        enqueue_init_state_for_connected_clients(force=True)
        registration_condition.notify_all()

    print(
        '[SLOT_BIND] transport=ws '
        f'router_session={short_session_id(router_session_id)} '
        f'requested={requested_slot if isinstance(requested_slot, str) else None} '
        f'expected={expected_slot} assigned={session.slot} '
        f'p1_expected={short_session_id(expected_p1_session_id)} '
        f'p2_expected={short_session_id(expected_p2_session_id)}'
    )

    if emit_fn is not None:
        emit_fn('registration_ok', {
            'ok': True,
            'slot': session.slot,
            'reconnect_token': session.reconnect_token,
            'both_players_connected': both_connected,
            'waiting_for_init': room_stage == 'init',
            'pending_replay_count': len(session.pending_commands),
        })

    # Deliver any immediately available packets to the registering client,
    # including the latest environment snapshot.
    if socketio is not None:
        session_packets = drain_pending_packets_for_session(session)
        if session_packets:
            socketio.emit(
                'protocol_packets',
                protocol_packets_emit_payload_for_slot(session.slot, session_packets),
                to=sid,
            )
            log_protocol_send(session_packets, session.slot)

    if both_connected and socketio is not None:
        connected_sids: list[str] = []
        for slot_name in ('p1', 'p2'):
            slot = cast(PlayerSlot, slot_name)
            peer_sid = transport_state.sid_by_slot[slot]
            if peer_sid is None:
                continue
            if peer_sid == sid:
                continue
            connected_sids.append(peer_sid)
            session_for_slot = transport_state.session_by_sid.get(peer_sid)
            if session_for_slot is None:
                continue
            peer_packets = drain_pending_packets_for_session(session_for_slot)
            if not peer_packets:
                continue
            socketio.emit(
                'protocol_packets',
                protocol_packets_emit_payload_for_slot(slot, peer_packets),
                to=peer_sid,
            )
            log_protocol_send(peer_packets, slot)

        for peer_sid in connected_sids:
            socketio.emit('opponent_reconnected', {
                'slot': session.slot,
                'both_players_connected': True,
            }, to=peer_sid)


def handle_protocol_socket_event(
    payload: Any,
    *,
    sid: str,
    packet_type: str,
    allow_body_data_fallback: bool,
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
    body = raw_body if isinstance(raw_body, dict) else (data if allow_body_data_fallback else {})

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
