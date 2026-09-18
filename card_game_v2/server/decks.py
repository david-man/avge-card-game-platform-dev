from __future__ import annotations

import random
from typing import Sequence

from ..avge_abstracts.AVGECard import AVGECard
from ..constants import CARDS_PER_DECK, User
from ..catalog import registry
from ..catalog.characters.strings.AshleyToby import AshleyToby
from ..catalog.characters.strings.EmilyWang import EmilyWang
from ..catalog.characters.piano.CathyRong import CathyRong
from ..catalog.characters.woodwinds.HarperAitken import HarperAitken
from ..catalog.characters.woodwinds.LucaChen import LucaChen
from ..catalog.characters.brass.BarronLee import BarronLee
from ..catalog.characters.percussion.KevinYang import KevinYang
from ..catalog.characters.choir.HappyRuthJara import HappyRuthJara
from ..catalog.characters.guitar.OwenLandry import OwenLandry

__all__ = ["CARDS_PER_DECK", "build_preset_decks", "build_game_deck"]

_POOL: list[type[AVGECard]] = [
    AshleyToby, AshleyToby, AshleyToby,
    EmilyWang, EmilyWang,
    CathyRong, CathyRong, CathyRong,
    HarperAitken, HarperAitken,
    LucaChen, LucaChen,
    BarronLee, BarronLee,
    KevinYang, KevinYang,
    HappyRuthJara, HappyRuthJara,
    OwenLandry, OwenLandry,
]

assert len(_POOL) == CARDS_PER_DECK


def build_preset_decks() -> dict[User, list[type[AVGECard]]]:
    '''Both players get the same fixed 20-card pool - used only as GameSession.__init__'s
    throwaway placeholder environment now (see GameSession.configure_decks()), never for a real
    match once both players have a real selected deck. Each player's own deck is independently
    shuffled so draw order varies per game.'''
    return {
        User.PLAYER_1: random.sample(_POOL, len(_POOL)),
        User.PLAYER_2: random.sample(_POOL, len(_POOL)),
    }


def build_game_deck(card_names: Sequence[str]) -> list[type[AVGECard]]:
    '''Resolves a saved deck's card_name list (server/deck_store.py's on-disk representation, and
    the same class_name identifier serialization.card_to_wire already uses everywhere) into real
    card classes and shuffles them - the single place a per-game deck's draw order gets
    randomized, mirroring build_preset_decks()'s own random.sample idiom. Raises KeyError naming
    the first unresolvable card - deck_rules.validate_deck_cards() is what should normally catch
    this before a deck is ever saved, so reaching this error means a saved deck outlived a catalog
    change.'''
    resolved: list[type[AVGECard]] = []
    for name in card_names:
        found = registry.card_class(name)
        if found is None:
            raise KeyError(f"Unknown card class in deck: {name!r}")
        resolved.append(found)
    return random.sample(resolved, len(resolved))
