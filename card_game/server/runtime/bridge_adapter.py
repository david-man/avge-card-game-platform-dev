from __future__ import annotations

from typing import Any
from card_game.server.server_types import JsonObject, CommandPayload


def extract_bridge_commands(bridge_result: JsonObject) -> tuple[list[JsonObject], JsonObject | None]:
    next_setup = bridge_result.get('setup_payload')
    resolved_setup = next_setup if isinstance(next_setup, dict) else None

    raw_commands = bridge_result.get('commands', [])
    raw_payloads = bridge_result.get('command_payloads', [])
    payloads = raw_payloads if isinstance(raw_payloads, list) else []

    extracted: list[JsonObject] = []
    for index, command in enumerate(raw_commands):
        if isinstance(command, dict):
            command_text = command.get('command')
            response_payload = command.get('response_payload')
        else:
            command_text = command
            response_payload = payloads[index] if index < len(payloads) else None

        if not isinstance(command_text, str) or not command_text.strip():
            continue

        extracted.append({
            'command': command_text.strip(),
            'response_payload': response_payload if isinstance(response_payload, dict) else None,
        })

    return extracted, resolved_setup


def bridge_requests_force_environment_sync(bridge_result: JsonObject) -> bool:
    return bool(bridge_result.get('force_environment_sync'))
