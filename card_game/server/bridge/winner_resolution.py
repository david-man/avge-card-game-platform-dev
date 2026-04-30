from __future__ import annotations

from typing import Any
from card_game.server.server_types import JsonObject, CommandPayload


def frontend_player_token(raw: Any) -> str | None:
    value = str(getattr(raw, 'value', raw)).strip().lower()
    if value in {'p1', 'player-1', 'player1'}:
        return 'player-1'
    if value in {'p2', 'player-2', 'player2'}:
        return 'player-2'
    return None


def player_from_frontend_token(bridge: Any, token: str):
    target_id = 'p1' if token == 'player-1' else 'p2'
    for player in bridge.env.players.values():
        player_id = str(getattr(getattr(player, 'unique_id', None), 'value', getattr(player, 'unique_id', ''))).lower()
        if player_id == target_id:
            return player
    return None


def normalize_winner_label(raw: str) -> str:
    return ' '.join(raw.strip().split())


def winner_label_for_token(bridge: Any, token: str, p1_username: str, p2_username: str) -> str:
    if token == 'player-1':
        return normalize_winner_label(p1_username)
    if token == 'player-2':
        return normalize_winner_label(p2_username)
    player = player_from_frontend_token(bridge, token)
    username = getattr(player, 'username', None) if player is not None else None
    if isinstance(username, str) and username.strip():
        return normalize_winner_label(username)
    return 'PLAYER 1' if token == 'player-1' else 'PLAYER 2'


def winner_command_from_surrender_payload(
    bridge: Any,
    data: JsonObject,
    p1_username: str,
    p2_username: str,
) -> str | None:
    loser_token = frontend_player_token(data.get('loser_view'))
    if loser_token is not None:
        winner_token = 'player-2' if loser_token == 'player-1' else 'player-1'
    else:
        winner_token = frontend_player_token(data.get('winner_view'))

    if winner_token is not None:
        winner_player = player_from_frontend_token(bridge, winner_token)
        if winner_player is not None:
            bridge.env.winner = winner_player
        winner_label = winner_label_for_token(bridge, winner_token, p1_username=p1_username, p2_username=p2_username)
        return f'winner {winner_token} {winner_label}'

    fallback_winner = data.get('winner')
    if isinstance(fallback_winner, str) and fallback_winner.strip():
        return f'winner {normalize_winner_label(fallback_winner)}'

    return None


def winner_command_from_environment(
    bridge: Any,
    p1_username: str,
    p2_username: str,
) -> str | None:
    winner = getattr(bridge.env, 'winner', None)
    winner_token = frontend_player_token(getattr(winner, 'unique_id', winner))
    if winner_token is None:
        return None
    winner_label = winner_label_for_token(bridge, winner_token, p1_username=p1_username, p2_username=p2_username)
    return f'winner {winner_token} {winner_label}'
