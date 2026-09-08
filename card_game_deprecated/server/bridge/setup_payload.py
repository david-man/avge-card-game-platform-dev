from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable
from card_game.server.server_types import JsonObject, CommandPayload

from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ...avge_abstracts.AVGECards import AVGECard, AVGEStadiumCard
from ...constants import Pile, PlayerID


def build_environment_from_default_setups(
    *,
    p1_setup: dict[Pile, list[type[AVGECard]]],
    p2_setup: dict[Pile, list[type[AVGECard]]],
    p1_username: str,
    p2_username: str,
    start_turn: PlayerID,
    starting_stadium: type[AVGEStadiumCard] | None,
    starting_stadium_player: PlayerID | None,
    round_number: int,
) -> AVGEEnvironment:
    return AVGEEnvironment(
        deepcopy(p1_setup),
        deepcopy(p2_setup),
        start_turn,
        p1_username=p1_username,
        p2_username=p2_username,
        starting_stadium=starting_stadium,
        starting_stadium_player=starting_stadium_player,
        start_round=round_number,
    )


def build_default_setup_payload_from_environment(
    *,
    build_environment: Callable[..., AVGEEnvironment],
    environment_to_setup_payload: Callable[[AVGEEnvironment], JsonObject],
    start_turn: PlayerID,
    starting_stadium: type[AVGEStadiumCard] | None,
    starting_stadium_player: PlayerID | None,
    round_number: int,
) -> JsonObject:
    env = build_environment(
        start_turn=start_turn,
        starting_stadium=starting_stadium,
        starting_stadium_player=starting_stadium_player,
        round_number=round_number,
    )
    return environment_to_setup_payload(env)


def environment_to_setup_payload(
    env: AVGEEnvironment,
    *,
    format_environment_to_setup_payload: Callable[[AVGEEnvironment], JsonObject],
    p1_username: str,
    p2_username: str,
) -> JsonObject:
    payload = format_environment_to_setup_payload(env)
    players = payload.get('players')
    if isinstance(players, dict):
        p1_payload = players.get('p1')
        p2_payload = players.get('p2')
        if isinstance(p1_payload, dict):
            p1_payload['username'] = p1_username
        if isinstance(p2_payload, dict):
            p2_payload['username'] = p2_username
    return payload


def environment_to_setup_json(
    env: AVGEEnvironment,
    *,
    format_environment_to_setup_json: Callable[[AVGEEnvironment, int], str],
    indent: int = 2,
) -> str:
    return format_environment_to_setup_json(env, indent)
