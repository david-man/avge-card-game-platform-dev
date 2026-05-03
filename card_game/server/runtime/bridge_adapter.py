from __future__ import annotations

from card_game.server.server_types import JsonObject


def extract_bridge_commands(bridge_result: JsonObject) -> tuple[list[JsonObject], JsonObject | None]:
    next_setup = bridge_result.get('setup_payload')
    resolved_setup = next_setup if isinstance(next_setup, dict) else None

    raw_commands = bridge_result.get('commands', [])
    if not isinstance(raw_commands, list):
        raw_commands = []

    extracted: list[JsonObject] = []
    for command in raw_commands:
        if not isinstance(command, dict):
            continue

        command_text = command.get('command')
        response_payload = command.get('response_payload')

        if not isinstance(command_text, str) or not command_text.strip():
            continue

        extracted.append({
            'command': command_text.strip(),
            'response_payload': response_payload if isinstance(response_payload, dict) else None,
        })

    return extracted, resolved_setup


def bridge_requests_force_environment_sync(bridge_result: JsonObject) -> bool:
    return bool(bridge_result.get('force_environment_sync'))
