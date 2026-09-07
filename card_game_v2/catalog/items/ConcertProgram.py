from __future__ import annotations

import random
from typing import cast

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard, AVGECharacterCard
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes
from ...core.EventCatalog import TransferCard, ReorderDeck
from ...core.AVGEIOManager import CardSelectionQuery, BroadcastIO, default_timeout
from ...engine.event import Event, Generator, Packet


class ConcertProgram(AVGEItemCard):
    '''Peek the top 5 of your deck, optionally take a character from among them to
    hand, then shuffle the deck.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    async def play_card(self, card: AVGECard, caller_action: ActionTypes) -> None:
        env = self.env
        player = env.players[self.owner]
        deck = player.card_piles[DeckType.DECK]
        hand = player.card_piles[DeckType.HAND]

        considered = list(deck.cards_holding[:5])
        character_choices = [c for c in considered if isinstance(c, AVGECharacterCard)]

        _id = AVGEEngineID(self, ActionTypes.NONCHAR, ConcertProgram)
        events: list[Event | Generator] = []

        if character_choices:
            picked = await env.report(CardSelectionQuery(
                self.owner,
                "Concert Program: Choose a character from the top 5 to reveal and take to hand.",
                1,
                cast(list[AVGECard], character_choices),
                considered,
                True,
                False,
            ), _id)
            if picked:
                picked_character = picked[0]
                events.append(TransferCard(_id, picked_character, deck, hand, env))
                await env.broadcast(BroadcastIO(
                    f"Concert Program: revealed and took {type(picked_character).__name__} to hand!",
                    default_timeout,
                ))

        def _shuffled_order(deck: AVGEDeck = deck):
            def gen() -> list[AVGECard]:
                return random.sample(deck.cards_holding, len(deck.cards_holding))
            return gen

        events.append(ReorderDeck(_id, deck, _shuffled_order(), env))
        env.push_packet(Packet(_id, events))
