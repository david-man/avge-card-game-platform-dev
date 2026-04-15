from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from flask import Flask, request

from .game_runner import FrontendGameBridge
from .logging import (
    log_protocol_ack_mismatch,
    log_protocol_event,
    log_protocol_recv,
    log_protocol_send,
    log_protocol_update,
)

app = Flask(__name__)
frontend_game_bridge = FrontendGameBridge()
entity_setup_payload: dict[str, Any] = frontend_game_bridge.get_setup_payload()
protocol_seq = 0
pending_input_command_for_ready: str | None = None
pending_notify_command_for_ready: str | None = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _issue_backend_packet(packet_type: str, body: dict[str, Any], is_response: bool) -> dict[str, Any]:
    global protocol_seq
    packet = {
        'SEQ': protocol_seq,
        'IsResponse': bool(is_response),
        'PacketType': packet_type,
        'Body': body,
    }
    protocol_seq += 1
    return packet


def _current_environment_body() -> dict[str, Any]:
    return deepcopy(entity_setup_payload) if isinstance(entity_setup_payload, dict) else {}


def _extract_bridge_commands(bridge_result: dict[str, Any]) -> list[str]:
    global entity_setup_payload
    next_setup = bridge_result.get('setup_payload')
    if isinstance(next_setup, dict):
        entity_setup_payload = next_setup

    return [
        command for command in bridge_result.get('commands', [])
        if isinstance(command, str) and command.strip()
    ]


def _commands_to_protocol_packets(commands: list[str], is_response: bool) -> list[dict[str, Any]]:
    global pending_input_command_for_ready
    global pending_notify_command_for_ready

    packets: list[dict[str, Any]] = []
    for command in commands:
        if command.startswith('input '):
            pending_input_command_for_ready = command
        if command.startswith('notify '):
            pending_notify_command_for_ready = command
        packets.append(
            _issue_backend_packet(
                'command',
                {
                    'command': command,
                },
                is_response=is_response,
            )
        )
    return packets


@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS, GET'
    return response


@app.get('/health')
def health() -> tuple[dict[str, str], int]:
    return {'status': 'ok', 'timestamp': _utc_now_iso()}, 200


@app.route('/protocol', methods=['POST', 'OPTIONS'])
def protocol() -> tuple[dict[str, Any], int]:
    global pending_input_command_for_ready
    global pending_notify_command_for_ready

    if request.method == 'OPTIONS':
        return {'ok': True}, 204

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return {'ok': False, 'error': 'Body must be a JSON object.'}, 400

    ack_raw = payload.get('ACK')
    packet_type_raw = payload.get('PacketType')
    body_raw = payload.get('Body', {})

    if not isinstance(ack_raw, int):
        return {'ok': False, 'error': 'ACK must be an integer.'}, 400

    if not isinstance(packet_type_raw, str) or packet_type_raw not in {
        'ready',
        'register_client',
        'update_frontend',
        'frontend_event',
    }:
        return {'ok': False, 'error': 'PacketType is invalid.'}, 400

    body = body_raw if isinstance(body_raw, dict) else {}

    log_protocol_recv(ack_raw, packet_type_raw, list(body.keys()))

    # Resync path: if ACK is stale, return authoritative environment snapshot.
    if packet_type_raw != 'register_client' and ack_raw != protocol_seq:
        log_protocol_ack_mismatch(ack_raw, protocol_seq, packet_type_raw)
        mismatch_packet = _issue_backend_packet('environment', _current_environment_body(), is_response=True)
        log_protocol_send([mismatch_packet])
        return {
            'ok': True,
            'packets': [mismatch_packet],
        }, 200

    packets: list[dict[str, Any]] = []

    if packet_type_raw == 'register_client':
        packets.append(
            _issue_backend_packet('environment', _current_environment_body(), is_response=True)
        )
        log_protocol_send(packets)
        return {'ok': True, 'packets': packets}, 200

    if packet_type_raw == 'ready':
        if isinstance(pending_input_command_for_ready, str) and pending_input_command_for_ready.strip():
            packets.append(
                _issue_backend_packet(
                    'command',
                    {'command': pending_input_command_for_ready},
                    is_response=True,
                )
            )
        elif isinstance(pending_notify_command_for_ready, str) and pending_notify_command_for_ready.strip():
            packets.append(
                _issue_backend_packet(
                    'command',
                    {'command': pending_notify_command_for_ready},
                    is_response=True,
                )
            )
        log_protocol_send(packets)
        return {'ok': True, 'packets': packets}, 200

    if packet_type_raw == 'update_frontend':
        command = body.get('command')
        input_response = body.get('input_response')
        notify_response = body.get('notify_response')

        log_protocol_update(
            isinstance(command, str) and bool(command.strip()),
            isinstance(input_response, dict),
            isinstance(notify_response, dict),
        )

        if isinstance(input_response, dict):
            bridge_result = frontend_game_bridge.handle_frontend_event(
                'input_result',
                input_response,
                {},
            )
            packets.extend(_commands_to_protocol_packets(_extract_bridge_commands(bridge_result), is_response=True))
            pending_input_command_for_ready = None

        if isinstance(command, str) and command.strip():
            if pending_input_command_for_ready == command:
                pending_input_command_for_ready = None
            if pending_notify_command_for_ready == command:
                pending_notify_command_for_ready = None

            bridge_result = frontend_game_bridge.handle_frontend_event(
                'terminal_log',
                {
                    'line': 'ACK backend_update_processed',
                    'command': command,
                },
                {},
            )
            packets.extend(_commands_to_protocol_packets(_extract_bridge_commands(bridge_result), is_response=True))

        log_protocol_send(packets)

        return {'ok': True, 'packets': packets}, 200

    # frontend_event
    event_name = body.get('event_type')
    response_data = body.get('response_data', {})
    context = body.get('context', {})

    if not isinstance(event_name, str) or not event_name.strip():
        return {'ok': False, 'error': 'frontend_event requires event_type.'}, 400

    bridge_result = frontend_game_bridge.handle_frontend_event(
        event_name,
        response_data if isinstance(response_data, dict) else {},
        context if isinstance(context, dict) else {},
    )
    packets.extend(_commands_to_protocol_packets(_extract_bridge_commands(bridge_result), is_response=True))
    log_protocol_event(
        event_name,
        list(response_data.keys()) if isinstance(response_data, dict) else [],
        list(context.keys()) if isinstance(context, dict) else [],
    )
    log_protocol_send(packets)
    return {'ok': True, 'packets': packets}, 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5500, debug=True)
