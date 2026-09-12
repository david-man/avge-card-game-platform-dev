from __future__ import annotations

import random

from ..avge_abstracts.AVGECard import AVGECard
from ..constants import User
from ..catalog.characters.strings.AshleyToby import AshleyToby
from ..catalog.characters.strings.EmilyWang import EmilyWang
from ..catalog.characters.piano.CathyRong import CathyRong
from ..catalog.characters.woodwinds.HarperAitken import HarperAitken
from ..catalog.characters.woodwinds.LucaChen import LucaChen
from ..catalog.characters.brass.BarronLee import BarronLee
from ..catalog.characters.percussion.KevinYang import KevinYang
from ..catalog.characters.choir.HappyRuthJara import HappyRuthJara
from ..catalog.characters.guitar.OwenLandry import OwenLandry

CARDS_PER_DECK = 20

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
    '''Both players get the same fixed 20-card pool - one attack-capable character class from
    most elements, no items/supporters for this first pass (nothing prevents adding them later;
    see core/AVGEIOManager.py's per-event update design, which needs no card-type restriction).
    Each player's own deck is independently shuffled so draw order varies per game.'''
    return {
        User.PLAYER_1: random.sample(_POOL, len(_POOL)),
        User.PLAYER_2: random.sample(_POOL, len(_POOL)),
    }
