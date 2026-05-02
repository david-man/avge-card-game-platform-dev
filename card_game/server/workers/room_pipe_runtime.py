from __future__ import annotations

import builtins
import json
import sys
from threading import RLock
from typing import Any


_ORIGINAL_PRINT = builtins.print


def _pipe_safe_print(*args: Any, **kwargs: Any) -> None:
    """Keep stdout reserved for JSON pipe messages only.

    The room worker reads this process stdout as newline-delimited JSON.
    Route normal prints to stderr so protocol log lines cannot corrupt the pipe.
    """

    target = kwargs.get('file')
    if target is None or target is sys.stdout:
        kwargs['file'] = sys.stderr
    _ORIGINAL_PRINT(*args, **kwargs)


builtins.print = _pipe_safe_print

import card_game.server.server as room_server


_write_lock = RLock()


def _write_message(message: dict[str, Any]) -> None:
    with _write_lock:
        sys.stdout.write(json.dumps(message, separators=(',', ':')) + '\n')
        sys.stdout.flush()


def _emit_event(event_type: str, payload: dict[str, Any]) -> None:
    _write_message({
        'type': 'event',
        'event_type': event_type,
        'payload': payload,
    })


def _emit_socket_event(event: str, payload: Any, to: str | None = None) -> None:
    body: dict[str, Any] = {
        'event': event,
        'payload': payload,
    }
    if isinstance(to, str) and to:
        body['to'] = to
    _emit_event('socket_emit', body)


class _PipeSocketBridge:
    def emit(self, event: str, payload: Any, to: str | None = None) -> None:
        _emit_socket_event(event, payload, to=to)


def _emit_fn_for_sid(sid: str):
    def _emit(event: str, payload: Any) -> None:
        _emit_socket_event(event, payload, to=sid)

    return _emit


def _pipe_notify_router_room_finished(reason: str) -> None:
    _emit_event('room_finished', {'reason': reason})


# Route all room-side socket emits through the worker pipe event stream.
room_server.socketio = _PipeSocketBridge()
# Replace legacy room->router HTTP callback with pipe event delivery.
room_server._notify_router_room_finished = _pipe_notify_router_room_finished


def _dispatch_command(method: str, params: dict[str, Any]) -> dict[str, Any]:
    if method == 'health':
        return {
            'status': 'ok',
            'timestamp': room_server._utc_now_iso(),
        }

    if method == 'register_client_or_play':
        sid_raw = params.get('sid')
        sid = sid_raw.strip() if isinstance(sid_raw, str) else ''
        if not sid:
            raise ValueError('register_client_or_play requires sid')

        payload = params.get('payload')
        room_server.runtime_register_client_or_play(
            payload,
            sid=sid,
            transport_lock=room_server.transport_lock,
            transport_state=room_server.transport_state,
            expected_p1_session_id=room_server.expected_p1_session_id,
            expected_p2_session_id=room_server.expected_p2_session_id,
            room_stage=room_server.room_stage,
            socketio=room_server.socketio,
            emit_fn=_emit_fn_for_sid(sid),
            expected_slot_for_router_session=room_server._expected_slot_for_router_session,
            recover_reconnect_token_for_expected_slot=room_server._recover_reconnect_token_for_expected_slot,
            cancel_disconnect_forfeit_timer_locked=room_server._cancel_disconnect_forfeit_timer_locked,
            mark_player_join_seen_locked=room_server._mark_player_join_seen_locked,
            enqueue_environment_for_connected_clients=room_server._enqueue_environment_for_connected_clients,
            enqueue_init_state_for_connected_clients=room_server._enqueue_init_state_for_connected_clients,
            registration_condition=room_server.registration_condition,
            short_session_id=room_server._short_session_id,
            drain_pending_packets_for_session=room_server._drain_pending_packets_for_session,
            protocol_packets_emit_payload_for_slot=room_server._protocol_packets_emit_payload_for_slot,
            log_protocol_send=room_server.log_protocol_send,
        )
        return {'ok': True}

    if method == 'protocol_socket_event':
        sid_raw = params.get('sid')
        sid = sid_raw.strip() if isinstance(sid_raw, str) else ''
        if not sid:
            raise ValueError('protocol_socket_event requires sid')

        packet_type_raw = params.get('packet_type')
        packet_type = packet_type_raw.strip() if isinstance(packet_type_raw, str) else ''
        if not packet_type:
            raise ValueError('protocol_socket_event requires packet_type')

        payload = params.get('payload')
        allow_body_data_fallback = params.get('allow_body_data_fallback') is True

        room_server.runtime_handle_protocol_socket_event(
            payload,
            sid=sid,
            packet_type=packet_type,
            allow_body_data_fallback=allow_body_data_fallback,
            transport_lock=room_server.transport_lock,
            transport_state=room_server.transport_state,
            process_protocol_packet=room_server._process_protocol_packet,
            protocol_packets_emit_payload_for_slot=room_server._protocol_packets_emit_payload_for_slot,
            emit_fn=_emit_fn_for_sid(sid),
        )
        return {'ok': True}

    if method == 'protocol_http_packet':
        payload = params.get('payload')
        if not isinstance(payload, dict):
            raise ValueError('protocol_http_packet requires payload object')

        response, status = room_server.runtime_handle_protocol_http(
            method='POST',
            payload=payload,
            normalize_client_slot=room_server._normalize_client_slot,
            process_protocol_packet=room_server._process_protocol_packet,
            augment_protocol_response_with_pending_peer_ack=room_server._augment_protocol_response_with_pending_peer_ack,
        )
        return {
            'status': status,
            'body': response,
        }

    if method == 'client_unloading':
        sid_raw = params.get('sid')
        sid = sid_raw.strip() if isinstance(sid_raw, str) else ''
        if not sid:
            raise ValueError('client_unloading requires sid')

        room_server.runtime_handle_client_unloading(
            sid=sid,
            handle_transport_sid_disconnect=lambda value: room_server._handle_transport_sid_disconnect(
                value,
                event_name='client_unloading',
            ),
            disconnect_fn=None,
        )
        return {'ok': True}

    if method == 'disconnect':
        sid_raw = params.get('sid')
        sid = sid_raw.strip() if isinstance(sid_raw, str) else ''
        if not sid:
            raise ValueError('disconnect requires sid')

        room_server.runtime_handle_disconnect(
            sid=sid,
            handle_transport_sid_disconnect=lambda value: room_server._handle_transport_sid_disconnect(
                value,
                event_name='disconnect',
            ),
        )
        return {'ok': True}

    if method == 'replace_room_session':
        payload = params.get('payload')
        if not isinstance(payload, dict):
            raise ValueError('replace_room_session requires payload object')

        (
            response,
            status,
            next_expected_p1_session_id,
            next_expected_p2_session_id,
            replaced_slot,
            evicted_sid,
        ) = room_server.runtime_replace_room_session(
            payload,
            transport_lock=room_server.transport_lock,
            transport_state=room_server.transport_state,
            expected_p1_session_id=room_server.expected_p1_session_id,
            expected_p2_session_id=room_server.expected_p2_session_id,
            cancel_disconnect_forfeit_timer_locked=room_server._cancel_disconnect_forfeit_timer_locked,
            reset_delivery_state_for_slot=room_server._reset_delivery_state_for_slot,
            registration_condition=room_server.registration_condition,
        )

        room_server.expected_p1_session_id = next_expected_p1_session_id
        room_server.expected_p2_session_id = next_expected_p2_session_id

        if status != 200:
            raise RuntimeError(str(response.get('error') or 'replace_room_session failed'))

        if isinstance(evicted_sid, str) and evicted_sid:
            _emit_socket_event(
                'session_replaced',
                {
                    'ok': True,
                    'slot': replaced_slot,
                    'reason': 'session_superseded',
                    'message': 'Signed out: account opened on another client.',
                },
                to=evicted_sid,
            )

        return response

    raise ValueError(f'Unsupported pipe command method: {method}')


def main() -> int:
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue

        try:
            message = json.loads(line)
        except Exception:
            continue

        if not isinstance(message, dict):
            continue

        if message.get('type') != 'command':
            continue

        request_id = message.get('id')
        if not isinstance(request_id, str) or not request_id:
            continue

        method = message.get('method')
        params = message.get('params')

        if not isinstance(method, str) or not method.strip() or not isinstance(params, dict):
            _write_message({
                'type': 'response',
                'id': request_id,
                'ok': False,
                'error': 'invalid command envelope',
            })
            continue

        try:
            result = _dispatch_command(method.strip(), params)
        except Exception as exc:
            _write_message({
                'type': 'response',
                'id': request_id,
                'ok': False,
                'error': str(exc),
            })
            continue

        _write_message({
            'type': 'response',
            'id': request_id,
            'ok': True,
            'result': result,
        })

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
