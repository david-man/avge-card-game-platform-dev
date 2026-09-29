from __future__ import annotations

from typing import cast

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard, AVGEToolCard, AVGEStadiumCard, Ability
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

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="ConcertRoster",
                description=ConcertRoster.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, ConcertRoster):
                raise TypeError("ConcertRoster action requires its defining card")
            env = acting_card.env
            player = env.players[acting_card.owner]
            deck = player.card_piles[DeckType.DECK]
            hand = player.card_piles[DeckType.HAND]

            considered = list(deck.cards_holding[:3])
            pick_choices = [c for c in considered if isinstance(c, (AVGEToolCard, AVGEStadiumCard))]
            if not pick_choices:
                return

            _id = AVGEEngineID(acting_card, self.action_type, ConcertRoster)
            picked = await env.report(CardSelectionQuery(
                acting_card.owner,
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
                f"Concert Roster: revealed and took {picked_card} to hand!",
                default_timeout,
            ))
