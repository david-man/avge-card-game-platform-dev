from __future__ import annotations

import random

from ...avge_abstracts.AVGECard import AVGECard, AVGEItemCard, AVGESupporterCard
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes
from ...core.EventCatalog import TransferCard, ReorderDeck
from ...engine.event import Event, Generator, Packet


class Will(AVGESupporterCard):
    '''Shuffle all of your discarded Item cards back into your deck.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    async def play_card(self, card: AVGECard, caller_action: ActionTypes) -> None:
        env = self.env
        player = env.players[self.owner]
        discard = player.card_piles[DeckType.DISCARD]
        deck = player.card_piles[DeckType.DECK]
        _id = AVGEEngineID(self, ActionTypes.NONCHAR, Will)

        items = [c for c in discard.cards_holding if isinstance(c, AVGEItemCard)]
        if not items:
            return

        events: list[Event | Generator] = [TransferCard(_id, c, discard, deck, env) for c in items]

        def _make_shuffle(deck: AVGEDeck = deck):
            def gen() -> list[AVGECard]:
                return random.sample(deck.cards_holding, len(deck.cards_holding))
            return gen
        events.append(ReorderDeck(_id, deck, _make_shuffle(), env))

        env.push_packet(Packet(_id, events))
