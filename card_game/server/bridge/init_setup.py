from __future__ import annotations

from typing import Any, Callable
from card_game.server.server_types import JsonObject, CommandPayload

from ...avge_abstracts.AVGECards import AVGECard, AVGECharacterCard
from ...constants import Pile


def build_player_setup_for_init(
    bridge: Any,
    slot: str,
    setup: JsonObject,
    *,
    blank_player_setup_fn: Callable[[], dict[Pile, list[type[AVGECard]]]],
    max_bench_size: int,
) -> dict[Pile, list[type[AVGECard]]]:
    if slot not in {'p1', 'p2'}:
        raise ValueError('init setup slot is invalid')

    player = bridge.env.players[slot]
    hand_holder = player.cardholders[Pile.HAND]
    bench_holder = player.cardholders[Pile.BENCH]
    active_holder = player.cardholders[Pile.ACTIVE]
    deck_holder = player.cardholders[Pile.DECK]
    discard_holder = player.cardholders[Pile.DISCARD]

    active_card_id_raw = setup.get('active_card_id')
    bench_card_ids_raw = setup.get('bench_card_ids')
    active_card_id = active_card_id_raw.strip() if isinstance(active_card_id_raw, str) else ''
    bench_card_ids = [
        card_id.strip()
        for card_id in bench_card_ids_raw
        if isinstance(card_id, str) and card_id.strip()
    ] if isinstance(bench_card_ids_raw, list) else []

    if not active_card_id:
        raise ValueError(f'{slot} init setup missing active card id')

    if len(bench_card_ids) > max_bench_size:
        raise ValueError(f'{slot} init setup exceeds bench size cap')

    selected_ids = [active_card_id, *bench_card_ids]
    if len(set(selected_ids)) != len(selected_ids):
        raise ValueError(f'{slot} init setup has duplicate selected card ids')

    candidate_by_id: dict[str, AVGECharacterCard] = {}
    for holder in (hand_holder, bench_holder, active_holder):
        for card in holder:
            if isinstance(card, AVGECharacterCard):
                candidate_by_id[card.unique_id] = card

    if active_card_id not in candidate_by_id:
        raise ValueError(f'{slot} init setup active card is not selectable')

    for bench_id in bench_card_ids:
        if bench_id not in candidate_by_id:
            raise ValueError(f'{slot} init setup bench card is not selectable')

    selected_id_set = set(selected_ids)

    resolved_setup = blank_player_setup_fn()
    resolved_setup[Pile.ACTIVE] = [type(candidate_by_id[active_card_id])]
    resolved_setup[Pile.BENCH] = [type(candidate_by_id[bench_id]) for bench_id in bench_card_ids]

    hand_cards: list[type[AVGECard]] = []
    for card in hand_holder:
        if isinstance(card, AVGECharacterCard) and card.unique_id in selected_id_set:
            continue
        hand_cards.append(type(card))

    for holder in (bench_holder, active_holder):
        for card in holder:
            if not isinstance(card, AVGECharacterCard):
                continue
            if card.unique_id in selected_id_set:
                continue
            hand_cards.append(type(card))

    resolved_setup[Pile.HAND] = hand_cards
    resolved_setup[Pile.DECK] = [type(card) for card in deck_holder]
    resolved_setup[Pile.DISCARD] = [type(card) for card in discard_holder]
    return resolved_setup
