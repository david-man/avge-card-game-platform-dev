from __future__ import annotations

from typing import Any
from card_game.server.server_types import JsonObject, CommandPayload
from typing import Callable

from ..models.server_models import MultiplayerTransportState


def apply_cors_headers(
    response: Any,
    *,
    request_origin: str | None,
    allowed_origins: list[str],
) -> Any:
    allowed_origin_set = set(allowed_origins)
    if allowed_origin_set and '*' not in allowed_origin_set:
        response.headers['Vary'] = 'Origin'
        if isinstance(request_origin, str) and request_origin.strip() and request_origin in allowed_origin_set:
            response.headers['Access-Control-Allow-Origin'] = request_origin
    else:
        if isinstance(request_origin, str) and request_origin.strip():
            response.headers['Access-Control-Allow-Origin'] = request_origin
            response.headers['Vary'] = 'Origin'
        else:
            response.headers['Access-Control-Allow-Origin'] = '*'

    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS, GET'
    allow_origin = response.headers.get('Access-Control-Allow-Origin', '')
    if allow_origin != '*':
        response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response


def health_response(*, utc_now_iso: Callable[[], str]) -> tuple[dict[str, str], int]:
    return {'status': 'ok', 'timestamp': utc_now_iso()}, 200


def handle_protocol_http(
    *,
    method: str,
    payload: Any,
    normalize_client_slot: Callable[[Any], str | None],
    process_protocol_packet: Callable[[JsonObject, str | None], tuple[JsonObject, int]],
    augment_protocol_response_with_pending_peer_ack: Callable[[JsonObject, str | None], JsonObject],
) -> tuple[JsonObject, int]:
    if method == 'OPTIONS':
        return {'ok': True}, 204

    if not isinstance(payload, dict):
        return {'ok': False, 'error': 'Body must be a JSON object.'}, 400

    client_slot = normalize_client_slot(payload.get('client_slot'))
    response, status = process_protocol_packet(payload, client_slot)
    return augment_protocol_response_with_pending_peer_ack(response, client_slot), status


def handle_scanner_input_http(
    *,
    method: str,
    payload: Any,
    normalize_scanner_command: Callable[[str], tuple[str, str]],
    enqueue_bridge_commands: Callable[[list[str], str | None], None],
    transport_lock: Any,
    transport_state: MultiplayerTransportState,
    log_protocol_event: Callable[[str, list[str], list[str], str | None], None],
) -> tuple[JsonObject, int]:
    if method == 'OPTIONS':
        return {'ok': True}, 204

    if not isinstance(payload, dict):
        return {'ok': False, 'error': 'Body must be a JSON object.'}, 400

    raw_command = payload.get('command')
    if not isinstance(raw_command, str) or not raw_command.strip():
        return {'ok': False, 'error': 'scanner command must be a non-empty string.'}, 400

    source = payload.get('source')
    source_label = source if isinstance(source, str) and source.strip() else 'scanner'

    try:
        action, normalized_command = normalize_scanner_command(raw_command)
    except ValueError as exc:
        return {'ok': False, 'error': str(exc)}, 400

    enqueue_bridge_commands([normalized_command], source_slot=None)

    with transport_lock:
        connected_slots = [
            slot_name
            for slot_name in ('p1', 'p2')
            if transport_state.sid_by_slot[slot_name] is not None
        ]

    log_protocol_event(
        'scanner_input',
        ['command', 'source', 'action'],
        ['normalized_command'],
        None,
    )

    return {
        'ok': True,
        'source': source_label,
        'action': action,
        'command': normalized_command,
        'connected_slots': connected_slots,
    }, 200
