from __future__ import annotations
from enum import Enum
from dataclasses import dataclass
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .AVGECard import AVGECard, AVGECharacterCard
    from .AVGEPlayer import AVGEPlayer


class DeckType(Enum):
    ACTIVE_CARD = 0
    BENCH = 1
    HAND = 2
    DECK = 3
    DISCARD = 4
    STADIUM = 5
    OFFHAND = 6 # for tools


@dataclass
class AVGEDeck:
    deck_owner : AVGEPlayer
    deck_type: DeckType
    cards_holding: list[AVGECard]
    def __len__(self):
        return len(self.cards_holding)
    def __getitem__(self, idx : int):
        return self.cards_holding[idx]
    def __setitem__(self, idx : int, value : AVGECard):
        self.cards_holding[idx] = value

@dataclass
class AVGEToolHolder(AVGEDeck):
    parent_card : AVGECharacterCard

def transfer_card(card: AVGECard, deck_from: AVGEDeck, deck_to: AVGEDeck):
    deck_from.cards_holding.remove(card)
    deck_to.cards_holding.append(card)
