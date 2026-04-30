from __future__ import annotations

from typing import Any

from .pending_input_query import (
    should_wait_for_ordering_result,
    should_wait_for_pending_input_result,
)
from ..logging import log_ack_trace_bridge


def pump_outbound_until_next_command(bridge: Any) -> None:
    if bridge._outbound_command_queue:
        return

    # Process at most one queued frontend event per ACK cycle.
    if bridge._pending_frontend_events:
        queued_event_name, queued_payload = bridge._pending_frontend_events.pop(0)
        bridge._enqueue_frontend_event_work(queued_event_name, queued_payload)
        return

    pending_ordering_map = getattr(bridge, '_pending_ordering_listener_by_token', None)
    if should_wait_for_ordering_result(
        pending_ordering_map=pending_ordering_map,
        pending_engine_input_args=bridge._pending_engine_input_args,
    ):
        pending_ordering_count = len(pending_ordering_map) if isinstance(pending_ordering_map, dict) else 0
        log_ack_trace_bridge(
            'waiting_for_ordering_result',
            pending_tokens=pending_ordering_count,
        )
        return

    waiting_for_pending_input_query = bridge._is_waiting_for_pending_input_query()
    if should_wait_for_pending_input_result(
        pending_engine_input_args=bridge._pending_engine_input_args,
        waiting_for_pending_input_query=waiting_for_pending_input_query,
    ):
        running_event = bridge._pending_input_query_event
        log_ack_trace_bridge(
            'waiting_for_input_result',
            input_keys=getattr(running_event, 'input_keys', None),
            input_type=getattr(running_event, 'input_type', None),
        )
        return

    # Perform one deterministic drain pass per ACK cycle.
    drain_input = bridge._pending_engine_input_args
    bridge._pending_engine_input_args = None
    drained_commands, drained_payloads = bridge._drain_engine(input_args=drain_input, stop_after_command_batch=True)
    if drained_commands:
        bridge._outbound_command_queue.extend(drained_commands)
        bridge._outbound_command_payload_queue.extend(drained_payloads)
        return

    log_ack_trace_bridge(
        'post_ack_no_commands',
        phase=bridge._frontend_phase_token(bridge.env.game_phase),
        event_running=(
            type(bridge.env._engine.event_running).__name__
            if bridge.env._engine.event_running is not None
            else None
        ),
        pending_input=bridge._pending_engine_input_args is not None,
    )
