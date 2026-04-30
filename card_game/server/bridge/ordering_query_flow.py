from __future__ import annotations

from typing import Any
from card_game.server.server_types import JsonObject, CommandPayload

from ...constants import OrderingQuery
from .input_queries import (
    build_ordering_listener_state,
    build_ordering_query_command,
    parse_ordered_selection_tokens,
    resolve_ordered_listeners,
    should_skip_duplicate_ordering_query,
)


def build_ordering_query_command_for_bridge(bridge: Any, query_data: OrderingQuery) -> str | None:
    unordered = list(getattr(query_data, 'unordered_listeners', []) or [])
    if len(unordered) == 0:
        bridge._clear_pending_ordering_query_state()
        return None

    listener_by_token, ordered_tokens, signature = build_ordering_listener_state(
        query_data,
        command_token=bridge._command_token,
    )

    if should_skip_duplicate_ordering_query(
        signature=signature,
        last_emitted_signature=bridge._last_emitted_ordering_query_signature,
        pending_listener_by_token=bridge._pending_ordering_listener_by_token,
        next_listener_by_token=listener_by_token,
    ):
        return None

    bridge._pending_ordering_listener_by_token = listener_by_token
    bridge._last_emitted_ordering_query_signature = signature

    player_token = bridge._player_id_to_frontend(bridge.env.player_turn.unique_id)
    return build_ordering_query_command(
        player_token=player_token,
        ordered_tokens=ordered_tokens,
    )


def parse_ordering_query_result_for_bridge(bridge: Any, data: JsonObject) -> JsonObject | None:
    pending_map = getattr(bridge, '_pending_ordering_listener_by_token', None)
    if not isinstance(pending_map, dict) or len(pending_map) == 0:
        return None

    ordered_tokens = parse_ordered_selection_tokens(data)
    if not isinstance(ordered_tokens, list):
        return None

    resolved_listeners = resolve_ordered_listeners(
        ordered_tokens,
        pending_map=pending_map,
    )
    if not isinstance(resolved_listeners, list):
        return None

    bridge._clear_pending_ordering_query_state()
    return {'group_ordering': resolved_listeners}
