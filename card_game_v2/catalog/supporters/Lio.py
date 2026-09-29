from __future__ import annotations

import random

from ...avge_abstracts.AVGECard import AVGECard, AVGESupporterCard, Ability
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes
from ...core.EventCatalog import TransferCard, ReorderDeck
from ...engine.event import Event, Generator, Packet


class Lio(AVGESupporterCard):
    '''Shuffle your hand into your deck, then draw 4. The "move hand to deck" step is
    lazy (evaluated only when this event actually runs, in a *later* packet than the
    one resolving this card's own play) rather than eagerly snapshotting
    `hand.cards_holding` up front - this card is itself still sitting in hand at the
    moment its NONCHAR action is invoked (it isn't discarded until after this returns), so
    an eager snapshot would incorrectly include Lio itself in the cards to shuffle.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="Lio",
                description=Lio.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, Lio):
                raise TypeError("Lio action requires its defining card")
            env = acting_card.env
            player = env.players[acting_card.owner]
            hand = player.card_piles[DeckType.HAND]
            deck = player.card_piles[DeckType.DECK]
            _id = AVGEEngineID(acting_card, self.action_type, Lio)

            def shuffle_hand_into_deck() -> list[Event | Generator]:
                hand_cards = list(hand.cards_holding)
                if not hand_cards:
                    return []
                events: list[Event | Generator] = [TransferCard(_id, c, hand, deck, env) for c in hand_cards]

                def gen() -> list[AVGECard]:
                    return random.sample(deck.cards_holding, len(deck.cards_holding))
                events.append(ReorderDeck(_id, deck, gen, env))
                return events

            def draw_one() -> list[Event | Generator]:
                if len(deck) == 0:
                    return []
                return [TransferCard(_id, deck.get_top(), deck, hand, env)]

            events: list[Event | Generator] = [shuffle_hand_into_deck]
            for _ in range(4):
                events.append(draw_one)

            env.push_packet(Packet(_id, events))
