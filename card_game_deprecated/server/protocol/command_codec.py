from __future__ import annotations

COMMAND_DELIMITER = ':;:'


def _sanitize_part(part: object) -> str:
    return str(part).replace(COMMAND_DELIMITER, ' ').strip()


def split_command(command: str) -> list[str]:
    normalized = command.strip()
    if not normalized:
        return []

    if COMMAND_DELIMITER in normalized:
        return [part.strip() for part in normalized.split(COMMAND_DELIMITER) if part.strip()]

    return normalized.split()


def command_action(command: str) -> str | None:
    parts = split_command(command)
    if not parts:
        return None
    return parts[0].lower()


def join_command(parts: list[str]) -> str:
    return COMMAND_DELIMITER.join(_sanitize_part(part) for part in parts)


def to_wire_command(command: str) -> str:
    parts = split_command(command)
    if not parts:
        return ''
    return join_command(parts)


def to_legacy_command(command: str) -> str:
    parts = split_command(command)
    if not parts:
        return ''
    return ' '.join(parts)
