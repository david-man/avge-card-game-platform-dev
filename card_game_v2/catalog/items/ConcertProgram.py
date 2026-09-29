from __future__ import annotations

import random
from typing import cast

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard, AVGECharacterCard, Ability
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

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="ConcertProgram",
                description=ConcertProgram.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, ConcertProgram):
                raise TypeError("ConcertProgram action requires its defining card")
            env = acting_card.env
            player = env.players[acting_card.owner]
            deck = player.card_piles[DeckType.DECK]
            hand = player.card_piles[DeckType.HAND]

            considered = list(deck.cards_holding[:5])
            character_choices = [c for c in considered if isinstance(c, AVGECharacterCard)]

            _id = AVGEEngineID(acting_card, self.action_type, ConcertProgram)
            events: list[Event | Generator] = []

            if character_choices:
                picked = await env.report(CardSelectionQuery(
                    acting_card.owner,
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
                        f"Concert Program: revealed and took {picked_character} to hand!",
                        default_timeout,
                    ))

            def _shuffled_order(deck: AVGEDeck = deck):
                def gen() -> list[AVGECard]:
                    return random.sample(deck.cards_holding, len(deck.cards_holding))
                return gen

            events.append(ReorderDeck(_id, deck, _shuffled_order(), env))
            env.push_packet(Packet(_id, events))
