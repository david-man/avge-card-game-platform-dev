from __future__ import annotations

from typing import Any
from card_game.server.server_types import JsonObject, CommandPayload

from ..logging import log_ack_wait


def build_frontend_event_response(
    bridge: Any,
    commands: list[str],
    command_payloads: list[CommandPayload],
) -> JsonObject:
    return {
        'commands': commands,
        'command_payloads': command_payloads,
        'setup_payload': bridge._current_setup_payload(),
        'force_environment_sync': bridge._consume_force_environment_sync_flag(),
    }


def handle_frontend_event_locked(
    bridge: Any,
    event_type: str,
    response_data: JsonObject | None,
    context: JsonObject | None,
) -> JsonObject:
    _ = context
    payload = response_data or {}
    event_name = bridge._canonical_event_name(event_type)

    if event_name == 'terminal_log':
        if bridge._accept_frontend_ack(payload):
            bridge._pump_outbound_until_next_command()
            commands, command_payloads = bridge._emit_next_command_if_ready()
            return build_frontend_event_response(bridge, commands, command_payloads)

        return build_frontend_event_response(bridge, [], [])

    if event_name in {'setup_loaded', 'resync_requested'}:
        bridge._queue_pending_input_query_resend()
        commands, command_payloads = bridge._emit_next_command_if_ready()
        return build_frontend_event_response(bridge, commands, command_payloads)

    if event_name == 'surrender_timeout':
        return build_frontend_event_response(bridge, [], [])

    # Command-level flow control: do not advance engine while waiting for
    # frontend ACK of the last emitted backend command.
    if bridge._awaiting_frontend_ack:
        bridge._pending_frontend_events.append((event_name, dict(payload)))

        log_ack_wait(
            queued_event=event_name,
            awaiting_command=bridge._awaiting_frontend_ack_command,
            queued_events=len(bridge._pending_frontend_events),
        )

        return build_frontend_event_response(bridge, [], [])

    bridge._enqueue_frontend_event_work(event_name, payload)
    commands, command_payloads = bridge._emit_next_command_if_ready()
    return build_frontend_event_response(bridge, commands, command_payloads)
