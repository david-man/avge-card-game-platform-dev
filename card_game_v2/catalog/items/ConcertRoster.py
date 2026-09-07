from __future__ import annotations

from typing import cast

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard, AVGEToolCard, AVGEStadiumCard
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes
from ...core.EventCatalog import TransferCard
from ...core.AVGEIOManager import CardSelectionQuery, BroadcastIO, default_timeout
from ...engine.event import Packet


class ConcertRoster(AVGEItemCard):
    '''Peek the top 3 of your deck; optionally take a tool or stadium from among them
    to hand.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    async def play_card(self, card: AVGECard, caller_action: ActionTypes) -> None:
        env = self.env
        player = env.players[self.owner]
        deck = player.card_piles[DeckType.DECK]
        hand = player.card_piles[DeckType.HAND]

        considered = list(deck.cards_holding[:3])
        pick_choices = [c for c in considered if isinstance(c, (AVGEToolCard, AVGEStadiumCard))]
        if not pick_choices:
            return

        _id = AVGEEngineID(self, ActionTypes.NONCHAR, ConcertRoster)
        picked = await env.report(CardSelectionQuery(
            self.owner,
            "Concert Roster: Choose a tool or stadium from the top 3 to take to hand.",
            1,
            cast(list[AVGECard], pick_choices),
            considered,
            True,
            False,
        ), _id)
        if not picked:
            return

        picked_card = picked[0]
        env.push_packet(Packet(_id, [TransferCard(_id, picked_card, deck, hand, env)]))
        await env.broadcast(BroadcastIO(
            f"Concert Roster: revealed and took {type(picked_card).__name__} to hand!",
            default_timeout,
        ))
