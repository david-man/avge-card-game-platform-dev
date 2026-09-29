from __future__ import annotations

import random
from typing import cast

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard, AVGESupporterCard, AVGEStadiumCard, Ability
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

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="Camera",
                description=Camera.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, Camera):
                raise TypeError("Camera action requires its defining card")
            env = acting_card.env
            player = env.players[acting_card.owner]
            discard = player.card_piles[DeckType.DISCARD]
            deck = player.card_piles[DeckType.DECK]

            eligible = [c for c in discard.cards_holding if isinstance(c, (AVGESupporterCard, AVGEStadiumCard))]
            if not eligible:
                return

            _id = AVGEEngineID(acting_card, self.action_type, Camera)
            picked = await env.report(CardSelectionQuery(
                acting_card.owner,
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
