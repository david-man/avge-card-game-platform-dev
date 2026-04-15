from __future__ import annotations

from typing import Any


def _format_value(value: Any) -> str:
    if isinstance(value, str):
        return repr(value)
    return str(value)


def _log_with_payload(prefix: str, payload: dict[str, Any]) -> None:
    formatted_fields = ' '.join(
        f'{key}={_format_value(value)}' for key, value in payload.items()
    )
    print(f'{prefix} {formatted_fields}'.rstrip())


def log_protocol_recv(
    ack: int,
    packet_type: str,
    body_keys: list[str],
    client_slot: str | None = None,
) -> None:
    _log_with_payload('[PROTOCOL][RECV]', {
        'ack': ack,
        'packet_type': packet_type,
        'body_keys': body_keys,
        'client_slot': client_slot,
    })


def log_protocol_ack_mismatch(
    ack: int,
    expected_seq: int,
    packet_type: str,
    client_slot: str | None = None,
) -> None:
    _log_with_payload('[PROTOCOL] ack_mismatch', {
        'ack': ack,
        'expected_seq': expected_seq,
        'packet_type': packet_type,
        'client_slot': client_slot,
    })


def log_protocol_send(packets: list[dict[str, Any]], client_slot: str | None = None) -> None:
    _log_with_payload('[PROTOCOL][SEND]', {
        'count': len(packets),
        'packets': [(packet.get('PacketType'), packet.get('SEQ')) for packet in packets],
        'client_slot': client_slot,
    })


def log_protocol_update(
    has_command: bool,
    has_input_response: bool,
    has_notify_response: bool,
    client_slot: str | None = None,
) -> None:
    _log_with_payload('[PROTOCOL][UPDATE]', {
        'has_command': has_command,
        'has_input_response': has_input_response,
        'has_notify_response': has_notify_response,
        'client_slot': client_slot,
    })


def log_protocol_event(
    event_name: str,
    response_data_keys: list[str],
    context_keys: list[str],
    client_slot: str | None = None,
) -> None:
    _log_with_payload('[PROTOCOL][EVENT]', {
        'event_name': event_name,
        'response_data_keys': response_data_keys,
        'context_keys': context_keys,
        'client_slot': client_slot,
    })


def log_ack_trace_bridge(event: str, **fields: Any) -> None:
    _log_with_payload(f'[ACK_TRACE][Bridge] {event}', fields)


def log_engine_response(
    stage: str,
    step: int,
    response_type: str,
    source_type: str,
    source: str,
    data_keys: list[str],
    has_input_args: bool,
) -> None:
    _log_with_payload('[ENGINE_RESPONSE]', {
        'stage': stage,
        'step': step,
        'type': response_type,
        'source_type': source_type,
        'source': source,
        'data_keys': data_keys,
        'has_input_args': has_input_args,
    })


def log_ack_wait(queued_event: str, awaiting_command: str | None, queued_events: int) -> None:
    _log_with_payload('[ACK_WAIT]', {
        'queued_event': queued_event,
        'awaiting_command': awaiting_command,
        'queued_events': queued_events,
    })


def log_energy_move(
    status: str,
    reason: str,
    running: str,
    game_phase: str,
    payload: dict[str, Any],
    attach_to: str | None = None,
    token: str | None = None,
) -> None:
    fields: dict[str, Any] = {
        'status': status,
        'reason': reason,
        'running': running,
        'game_phase': game_phase,
        'payload': payload,
    }
    if attach_to is not None:
        fields['attach_to'] = attach_to
    if token is not None:
        fields['token'] = token
    _log_with_payload('[ENERGY_MOVE]', fields)
