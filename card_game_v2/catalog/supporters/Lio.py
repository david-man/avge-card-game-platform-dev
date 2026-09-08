from __future__ import annotations

import random

from ...avge_abstracts.AVGECard import AVGECard, AVGESupporterCard
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
    moment `play_card()` is called (it isn't discarded until after this returns), so
    an eager snapshot would incorrectly include Lio itself in the cards to shuffle.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    async def play_card(self, card: AVGECard, caller_action: ActionTypes) -> None:
        env = self.env
        player = env.players[self.owner]
        hand = player.card_piles[DeckType.HAND]
        deck = player.card_piles[DeckType.DECK]
        _id = AVGEEngineID(self, ActionTypes.NONCHAR, Lio)

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
