from __future__ import annotations

import random

from ...avge_abstracts.AVGECard import AVGECard, AVGESupporterCard
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes
from ...core.EventCatalog import TransferCard, ReorderDeck
from ...engine.event import Event, Generator, Packet


class Richard(AVGESupporterCard):
    '''Swap your discard and deck piles entirely; each ends up independently
    reshuffled. Both piles' contents are snapshotted before any transfers happen,
    since transferring discard->deck first would otherwise contaminate the "original
    deck" snapshot needed for the second half of the swap.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    async def play_card(self, card: AVGECard, caller_action: ActionTypes) -> None:
        env = self.env
        player = env.players[self.owner]
        discard = player.card_piles[DeckType.DISCARD]
        deck = player.card_piles[DeckType.DECK]
        _id = AVGEEngineID(self, ActionTypes.NONCHAR, Richard)

        original_discard = list(discard.cards_holding)
        original_deck = list(deck.cards_holding)
        if not original_discard and not original_deck:
            return

        events: list[Event | Generator] = []
        events.extend(TransferCard(_id, c, discard, deck, env) for c in original_discard)
        events.extend(TransferCard(_id, c, deck, discard, env) for c in original_deck)

        def _shuffle_deck() -> list[AVGECard]:
            return random.sample(deck.cards_holding, len(deck.cards_holding))
        events.append(ReorderDeck(_id, deck, _shuffle_deck, env))

        def _shuffle_discard() -> list[AVGECard]:
            return random.sample(discard.cards_holding, len(discard.cards_holding))
        events.append(ReorderDeck(_id, discard, _shuffle_discard, env))

        env.push_packet(Packet(_id, events))
