from __future__ import annotations

from typing import Any
from card_game.server.server_types import JsonObject, CommandPayload

from ...internal_events import InputEvent
from ..logging import log_ack_trace_bridge


def clear_pending_input_query_state() -> tuple[None, None]:
    return None, None


def is_waiting_for_pending_input_query(
    *,
    pending_event: Any,
    running_event: Any,
) -> bool:
    return isinstance(pending_event, InputEvent) and running_event is pending_event


def is_waiting_for_pending_input_query_for_bridge(bridge: Any) -> bool:
    pending_event = bridge._pending_input_query_event
    if not isinstance(pending_event, InputEvent):
        return False

    running_event = getattr(bridge.env._engine, 'event_running', None)
    if is_waiting_for_pending_input_query(
        pending_event=pending_event,
        running_event=running_event,
    ):
        return True

    bridge._clear_pending_input_query_state()
    return False


def normalize_pending_input_query_command(pending_command: Any) -> str | None:
    if not isinstance(pending_command, str):
        return None
    normalized = pending_command.strip()
    return normalized if normalized else None


def is_pending_input_query_in_flight(
    *,
    awaiting_frontend_ack: bool,
    awaiting_frontend_ack_command: Any,
    pending_command: str,
) -> bool:
    if not awaiting_frontend_ack:
        return False
    if not isinstance(awaiting_frontend_ack_command, str):
        return False
    return awaiting_frontend_ack_command.strip() == pending_command


def is_pending_input_query_already_queued(
    *,
    outbound_command_queue: list[str],
    pending_command: str,
) -> bool:
    return any(
        isinstance(command, str) and command.strip() == pending_command
        for command in outbound_command_queue
    )


def should_wait_for_ordering_result(
    *,
    pending_ordering_map: Any,
    pending_engine_input_args: JsonObject | None,
) -> bool:
    return isinstance(pending_ordering_map, dict) and bool(pending_ordering_map) and pending_engine_input_args is None


def should_wait_for_pending_input_result(
    *,
    pending_engine_input_args: JsonObject | None,
    waiting_for_pending_input_query: bool,
) -> bool:
    return pending_engine_input_args is None and waiting_for_pending_input_query


def queue_pending_input_query_resend(bridge: Any) -> bool:
    if not bridge._is_waiting_for_pending_input_query():
        return False

    normalized_pending_command = normalize_pending_input_query_command(
        bridge._pending_input_query_command,
    )
    if not isinstance(normalized_pending_command, str):
        bridge._clear_pending_input_query_state()
        return False

    if is_pending_input_query_in_flight(
        awaiting_frontend_ack=bridge._awaiting_frontend_ack,
        awaiting_frontend_ack_command=bridge._awaiting_frontend_ack_command,
        pending_command=normalized_pending_command,
    ):
        log_ack_trace_bridge(
            'pending_input_query_resend_skipped_in_flight',
            command=normalized_pending_command,
        )
        return False

    if is_pending_input_query_already_queued(
        outbound_command_queue=bridge._outbound_command_queue,
        pending_command=normalized_pending_command,
    ):
        return False

    # Intentional resend path for reconnect/resync flows.
    bridge._outbound_command_queue.insert(0, normalized_pending_command)
    bridge._outbound_command_payload_queue.insert(0, None)
    log_ack_trace_bridge(
        'pending_input_query_resent',
        command=normalized_pending_command,
    )
    return True
