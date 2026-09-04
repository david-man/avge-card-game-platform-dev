from __future__ import annotations
from typing import TYPE_CHECKING, Any
from ..constants import User, AVGEPlayerAttribute
if TYPE_CHECKING:
    from .AVGEEnvironment import AVGEEnvironment
    from .AVGEDeck import AVGEDeck, DeckType


class AVGEPlayer:
    def __init__(self, id: User, card_piles: dict[DeckType, AVGEDeck], env: AVGEEnvironment):
        self.env = env
        self.id = id
        self.card_piles = card_piles
        self.attributes : dict[AVGEPlayerAttribute, int] = {
            AVGEPlayerAttribute.ENERGY_ADD_REMAINING_IN_TURN: 0,
            AVGEPlayerAttribute.KO_COUNT: 0,
            AVGEPlayerAttribute.SUPPORTER_USES_REMAINING_IN_TURN: 0,
            AVGEPlayerAttribute.SWAP_REMAINING_IN_TURN: 0,
            AVGEPlayerAttribute.ATTACKS_LEFT: 0,
        }
    def cache_set(self, key: str, new_value: Any):
        self.env.cache_set(self, key, new_value)

    def cache_delete(self, key: str):
        self.env.cache_delete(self, key)
