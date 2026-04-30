from __future__ import annotations

from typing import Any, Callable

from ...avge_abstracts.AVGEEvent import Notify, RevealCards, RevealStr
from ...constants import PlayerID


def normalize_notify_timeout(timeout: int | None) -> int:
    if timeout is None:
        return -1
    try:
        parsed = int(timeout)
    except Exception:
        return -1
    return parsed if parsed >= -1 else -1


def notify_targets_from_players(
    players: list[PlayerID],
    *,
    player_id_to_frontend: Callable[[PlayerID], str],
) -> list[str]:
    targets: list[str] = []
    for player in players:
        token = player_id_to_frontend(player)
        if token not in targets:
            targets.append(token)
    return targets


def notify_from_notify(
    notify_data: Notify,
    *,
    notify_targets_from_players_fn: Callable[[list[PlayerID]], list[str]],
    notify_both: Callable[[str, int], list[str]],
    command_token: Callable[[str], str],
    normalize_timeout: Callable[[int | None], int] = normalize_notify_timeout,
) -> list[str]:
    timeout = normalize_timeout(notify_data.timeout)
    targets = notify_targets_from_players_fn(notify_data.players)
    if not targets or len(targets) >= 2:
        return notify_both(notify_data.message, timeout)
    return [
        f'notify {target} {command_token(notify_data.message)} {timeout}'
        for target in targets
    ]


def reveal_commands_for_players(
    players: list[PlayerID],
    card_ids: list[str],
    message: str | None = None,
    timeout: int | None = None,
    *,
    notify_targets_from_players_fn: Callable[[list[PlayerID]], list[str]],
    command_token: Callable[[str], str],
    normalize_timeout: Callable[[int | None], int] = normalize_notify_timeout,
) -> list[str]:
    if len(card_ids) == 0:
        return []

    cards_csv = ','.join(card_ids)
    message_token = command_token(message) if isinstance(message, str) and message.strip() else None
    timeout_token = normalize_timeout(timeout)
    targets = notify_targets_from_players_fn(players)
    target_token = 'both' if len(targets) >= 2 or len(targets) == 0 else targets[0]

    if isinstance(message_token, str):
        return [f'reveal {target_token} [{cards_csv}] {message_token} {timeout_token}']
    return [f'reveal {target_token} [{cards_csv}] {timeout_token}']


def notification_commands_from_payload(
    payload: Any,
    *,
    notify_from_notify_fn: Callable[[Notify], list[str]],
    reveal_commands_for_players_fn: Callable[[list[PlayerID], list[str], str | None, int | None], list[str]],
) -> list[str]:
    if isinstance(payload, RevealCards):
        card_ids = [getattr(card, 'unique_id', str(card)) for card in payload.cards]
        return reveal_commands_for_players_fn(payload.players, card_ids, payload.message, payload.timeout)

    if isinstance(payload, RevealStr):
        msg = f"{payload.message}: {', '.join(payload.items)}" if len(payload.items) > 0 else payload.message
        return notify_from_notify_fn(Notify(msg, payload.players, payload.timeout))

    if isinstance(payload, Notify):
        return notify_from_notify_fn(payload)

    return []
