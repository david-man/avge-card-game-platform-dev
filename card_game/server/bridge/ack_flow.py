from __future__ import annotations

from typing import Any
from card_game.server.server_types import JsonObject, CommandPayload

from ...avge_abstracts.AVGEEnvironment import GamePhase
from ..logging import log_ack_trace_bridge


def accept_frontend_ack(bridge: Any, payload: JsonObject) -> bool:
    if not bridge._awaiting_frontend_ack:
        if str(payload.get('line', '')).strip().lower() == 'ack backend_update_processed':
            log_ack_trace_bridge('unexpected_ack_no_wait')
        return False

    ack_line = str(payload.get('line', '')).strip().lower()
    if ack_line != 'ack backend_update_processed':
        return False

    expected = bridge._awaiting_frontend_ack_command
    ack_command = payload.get('command')

    # Strict ACK mode: every emitted backend command must be explicitly
    # acknowledged with a matching command payload.
    if expected is not None and (
        not isinstance(ack_command, str)
        or ack_command.strip() != expected.strip()
    ):
        log_ack_trace_bridge(
            'ack_rejected_command_mismatch',
            expected=expected,
            actual=ack_command,
        )
        return False

    log_ack_trace_bridge('ack_accepted', command=expected)
    bridge._awaiting_frontend_ack = False
    bridge._awaiting_frontend_ack_command = None
    return True


def emit_next_command_if_ready(bridge: Any) -> tuple[list[str], list[CommandPayload]]:
    if bridge._awaiting_frontend_ack:
        return [], []
    if not bridge._outbound_command_queue:
        return [], []

    next_command = bridge._outbound_command_queue.pop(0)
    next_payload = bridge._outbound_command_payload_queue.pop(0) if bridge._outbound_command_payload_queue else None
    bridge._awaiting_frontend_ack = True
    bridge._awaiting_frontend_ack_command = next_command
    log_ack_trace_bridge(
        'emit_command_waiting_ack',
        command=next_command,
        remaining_queue=len(bridge._outbound_command_queue),
    )
    return [next_command], [next_payload]


def append_phase_command_if_changed(bridge: Any, commands: list[str], phase: GamePhase) -> None:
    phase_token = bridge._frontend_phase_token(phase)
    if bridge._last_emitted_phase_token == phase_token:
        return
    commands.append(f'phase {phase_token}')
    bridge._last_emitted_phase_token = phase_token
