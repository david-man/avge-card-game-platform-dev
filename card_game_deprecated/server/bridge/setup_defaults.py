from __future__ import annotations

from random import sample
from typing import Any, Callable, Mapping
import json
import os

from ...avge_abstracts.AVGECards import AVGECard, AVGECharacterCard
from ...constants import Pile


def blank_player_setup() -> dict[Pile, list[type[AVGECard]]]:
    return {
        Pile.ACTIVE: [],
        Pile.BENCH: [],
        Pile.HAND: [],
        Pile.DISCARD: [],
        Pile.DECK: [],
        Pile.TOOL: [],
        Pile.STADIUM: [],
    }


def resolve_catalog_card_class(
    card_id: str,
    *,
    symbol_lookup: Mapping[str, Any],
) -> type[AVGECard] | None:
    symbol = symbol_lookup.get(card_id)
    if not isinstance(symbol, type):
        return None
    if not issubclass(symbol, AVGECard):
        return None
    return symbol


def selected_cards_from_env(
    env_name: str,
    *,
    resolver: Callable[[str], type[AVGECard] | None],
) -> list[type[AVGECard]]:
    raw_payload = os.getenv(env_name, '')
    if not raw_payload:
        return []

    try:
        parsed = json.loads(raw_payload)
    except Exception:
        return []

    if not isinstance(parsed, list):
        return []

    resolved: list[type[AVGECard]] = []
    for raw_card_id in parsed:
        if not isinstance(raw_card_id, str) or not raw_card_id.strip():
            continue
        resolved_class = resolver(raw_card_id.strip())
        if resolved_class is not None:
            resolved.append(resolved_class)
    return resolved


def apply_selected_cards_to_setup(
    selected_cards: list[type[AVGECard]],
    *,
    initial_hand_size: int,
) -> dict[Pile, list[type[AVGECard]]]:
    resolved_setup = blank_player_setup()
    remaining_cards = list(selected_cards)

    character_cards = [card for card in remaining_cards if issubclass(card, AVGECharacterCard)]
    if not character_cards:
        return resolved_setup

    active_card = sample(character_cards, 1)[0]
    remaining_cards.remove(active_card)
    resolved_setup[Pile.ACTIVE] = [active_card]

    hand_count = min(initial_hand_size, len(remaining_cards))
    initial_hand = sample(remaining_cards, hand_count) if hand_count > 0 else []
    for card in initial_hand:
        remaining_cards.remove(card)

    resolved_setup[Pile.HAND] = initial_hand
    resolved_setup[Pile.DECK] = remaining_cards
    return resolved_setup
