from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .server_models import ClientSession


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_client_slot(raw_slot: Any) -> str | None:
    return raw_slot if isinstance(raw_slot, str) and raw_slot in {'p1', 'p2'} else None


def extract_client_slot_hint(body: dict[str, Any], normalize_slot=normalize_client_slot) -> str | None:
    if not isinstance(body, dict):
        return None

    direct_slot = normalize_slot(body.get('client_slot'))
    if direct_slot is not None:
        return direct_slot

    context = body.get('context')
    if isinstance(context, dict):
        context_slot = normalize_slot(context.get('client_slot'))
        if context_slot is not None:
            return context_slot

    response_data = body.get('response_data')
    if isinstance(response_data, dict):
        response_slot = normalize_slot(response_data.get('client_slot'))
        if response_slot is not None:
            return response_slot

    return None


def issue_backend_packet(
    protocol_seq: int,
    packet_type: str,
    body: dict[str, Any],
    is_response: bool,
) -> tuple[dict[str, Any], int]:
    packet = {
        'SEQ': protocol_seq,
        'IsResponse': bool(is_response),
        'PacketType': packet_type,
        'Body': body,
    }
    return packet, protocol_seq + 1


def issue_backend_packet_for_session(
    session: ClientSession,
    packet_type: str,
    body: dict[str, Any],
    is_response: bool,
) -> dict[str, Any]:
    packet = {
        'SEQ': session.next_seq,
        'IsResponse': bool(is_response),
        'PacketType': packet_type,
        'Body': body,
    }
    session.next_seq += 1
    return packet


def build_packet_blueprint(packet_type: str, body: dict[str, Any], is_response: bool) -> dict[str, Any]:
    return {
        'IsResponse': bool(is_response),
        'PacketType': packet_type,
        'Body': body,
    }


def drain_pending_packets_for_session(
    session: ClientSession,
    issue_packet_for_session=issue_backend_packet_for_session,
) -> list[dict[str, Any]]:
    drained: list[dict[str, Any]] = []
    for pending in session.pending_packets:
        packet_type = pending.get('PacketType')
        body = pending.get('Body')
        is_response = pending.get('IsResponse', True)
        if isinstance(packet_type, str) and isinstance(body, dict):
            if packet_type == 'environment':
                session.environment_initialized = True
            drained.append(
                issue_packet_for_session(
                    session,
                    packet_type,
                    body,
                    bool(is_response),
                )
            )
    session.pending_packets = []
    return drained
