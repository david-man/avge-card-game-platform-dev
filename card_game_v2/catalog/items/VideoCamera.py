from __future__ import annotations

from typing import cast

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard, Ability
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes, default_timeout
from ...core.EventCatalog import TransferCard, ReorderDeck
from ...core.AVGEIOManager import CardSelectionQuery, Notification
from ...engine.event import Event, Generator, Packet


class VideoCamera(AVGEItemCard):
    '''Move a chosen own discard item to the very top of the deck when one is available.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="VideoCamera",
                description=VideoCamera.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, VideoCamera):
                raise TypeError("VideoCamera action requires its defining card")
            env = acting_card.env
            player = env.players[acting_card.owner]
            discard = player.card_piles[DeckType.DISCARD]
            deck = player.card_piles[DeckType.DECK]

            discard_items = [c for c in discard.cards_holding if isinstance(c, AVGEItemCard)]
            if not discard_items:
                await env.report(Notification(
                    acting_card.owner,
                    "Video Camera found no Item in your discard to move.",
                    default_timeout,
                ), AVGEEngineID(acting_card, self.action_type, VideoCamera))
                return

            _id = AVGEEngineID(acting_card, self.action_type, VideoCamera)
            picked = await env.report(CardSelectionQuery(
                acting_card.owner,
                "Video Camera: Choose an item in your discard to move to the top of your deck.",
                1,
                cast(list[AVGECard], discard_items),
                list(discard.cards_holding),
                False,
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
