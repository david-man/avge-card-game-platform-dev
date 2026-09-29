from __future__ import annotations

import random

from ...avge_abstracts.AVGECard import AVGECard, AVGEItemCard, AVGESupporterCard, Ability
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes
from ...core.EventCatalog import TransferCard, ReorderDeck
from ...engine.event import Event, Generator, Packet


class Will(AVGESupporterCard):
    '''Shuffle all of your discarded Item cards back into your deck.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="Will",
                description=Will.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, Will):
                raise TypeError("Will action requires its defining card")
            env = acting_card.env
            player = env.players[acting_card.owner]
            discard = player.card_piles[DeckType.DISCARD]
            deck = player.card_piles[DeckType.DECK]
            _id = AVGEEngineID(acting_card, self.action_type, Will)

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
