from __future__ import annotations

import random
from typing import cast

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard, AVGESupporterCard, AVGEStadiumCard
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes
from ...core.EventCatalog import TransferCard, ReorderDeck
from ...core.AVGEIOManager import CardSelectionQuery
from ...engine.event import Event, Generator, Packet


class Camera(AVGEItemCard):
    '''Optionally shuffle a chosen own Supporter or Stadium from discard into the deck
    at a random position.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    async def play_card(self, card: AVGECard, caller_action: ActionTypes) -> None:
        env = self.env
        player = env.players[self.owner]
        discard = player.card_piles[DeckType.DISCARD]
        deck = player.card_piles[DeckType.DECK]

        eligible = [c for c in discard.cards_holding if isinstance(c, (AVGESupporterCard, AVGEStadiumCard))]
        if not eligible:
            return

        _id = AVGEEngineID(self, ActionTypes.NONCHAR, Camera)
        picked = await env.report(CardSelectionQuery(
            self.owner,
            "Camera: Choose a Supporter or Stadium from discard to shuffle into your deck.",
            1,
            cast(list[AVGECard], eligible),
            list(discard.cards_holding),
            True,
            False,
        ), _id)
        if not picked:
            return

        chosen = picked[0]

        def _reordering_with_chosen_shuffled_in(deck: AVGEDeck = deck, chosen: AVGECard = chosen):
            def gen() -> list[AVGECard]:
                rest = [c for c in deck.cards_holding if c is not chosen]
                idx = random.randint(0, len(rest))
                rest.insert(idx, chosen)
                return rest
            return gen

        events: list[Event | Generator] = [
            TransferCard(_id, chosen, discard, deck, env),
            ReorderDeck(_id, deck, _reordering_with_chosen_shuffled_in(), env),
        ]
        env.push_packet(Packet(_id, events))
