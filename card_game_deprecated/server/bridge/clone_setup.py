from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable
from card_game.server.server_types import JsonObject, CommandPayload


def clone_with_init_setup(
    bridge: Any,
    setup_by_slot: dict[str, JsonObject],
    *,
    environment_factory: Callable[..., Any],
    bridge_factory: Callable[..., Any],
) -> Any:
    with bridge._lock:
        p1_setup = bridge._build_player_setup_for_init('p1', setup_by_slot.get('p1', {}))
        p2_setup = bridge._build_player_setup_for_init('p2', setup_by_slot.get('p2', {}))
        next_env = environment_factory(
            deepcopy(p1_setup),
            deepcopy(p2_setup),
            bridge.env.player_turn.unique_id,
            p1_username=bridge.env.players['p1'].username,
            p2_username=bridge.env.players['p2'].username,
            start_round=bridge.env.round_id,
        )

    return bridge_factory(env=next_env)
