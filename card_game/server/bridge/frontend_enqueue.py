from __future__ import annotations

from typing import Any
from card_game.server.server_types import JsonObject, CommandPayload


def enqueue_frontend_event_work(bridge: Any, event_name: str, payload: JsonObject) -> None:
    commands, used_input = bridge._apply_frontend_event(event_name, payload)
    bridge._outbound_command_queue.extend(commands)
    bridge._outbound_command_payload_queue.extend([None] * len(commands))

    if used_input is not None:
        bridge._pending_engine_input_args = used_input

    if not bridge._outbound_command_queue:
        drain_input = bridge._pending_engine_input_args
        bridge._pending_engine_input_args = None
        drained_commands, drained_payloads = bridge._drain_engine(input_args=drain_input, stop_after_command_batch=True)
        bridge._outbound_command_queue.extend(drained_commands)
        bridge._outbound_command_payload_queue.extend(drained_payloads)
