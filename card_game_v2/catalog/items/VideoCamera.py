from __future__ import annotations

from typing import cast

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes
from ...core.EventCatalog import TransferCard, ReorderDeck
from ...core.AVGEIOManager import CardSelectionQuery
from ...engine.event import Event, Generator, Packet


class VideoCamera(AVGEItemCard):
    '''Optionally move a chosen own discard item to the very top of the deck.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    async def play_card(self, card: AVGECard, caller_action: ActionTypes) -> None:
        env = self.env
        player = env.players[self.owner]
        discard = player.card_piles[DeckType.DISCARD]
        deck = player.card_piles[DeckType.DECK]

        discard_items = [c for c in discard.cards_holding if isinstance(c, AVGEItemCard)]
        if not discard_items:
            return

        _id = AVGEEngineID(self, ActionTypes.NONCHAR, VideoCamera)
        picked = await env.report(CardSelectionQuery(
            self.owner,
            "Video Camera: Choose an item in your discard to move to the top of your deck (or None).",
            1,
            cast(list[AVGECard], discard_items),
            list(discard.cards_holding),
            True,
            False,
        ), _id)
        if not picked:
            return

        chosen = picked[0]

        def _reordering_to_top(deck: AVGEDeck = deck, chosen: AVGECard = chosen):
            def gen() -> list[AVGECard]:
                return [chosen] + [c for c in deck.cards_holding if c is not chosen]
            return gen

        events: list[Event | Generator] = [
            TransferCard(_id, chosen, discard, deck, env),
            ReorderDeck(_id, deck, _reordering_to_top(), env),
        ]
        env.push_packet(Packet(_id, events))
