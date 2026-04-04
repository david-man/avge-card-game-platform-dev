from __future__ import annotations

import random

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *


class JoshuaKou(AVGECharacterCard):
    _LAST_ATK1_ROUND_KEY = "joshuakou_atk1_last_round"

    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.PIANO, 1, 1)
        self.has_atk_1 = True
        self.atk_1_cost = 1
        self.has_atk_2 = False
        self.has_passive = False
        self.has_active = True

    @staticmethod
    def can_play_active(card: AVGECharacterCard) -> bool:
        hand = card.player.cardholders[Pile.HAND]
        return len(hand) == 1 and hand.peek() == card

    @staticmethod
    def active(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import TransferCard, EmptyEvent

        hand = card.player.cardholders[Pile.HAND]
        deck = card.player.cardholders[Pile.DECK]

        def generate_packet():
            if card not in hand:
                return [EmptyEvent("JoshuaKou active failed: card not in hand.", ActionTypes.ACTIVATE_ABILITY, card)]
            packet = [TransferCard(card, hand, deck, ActionTypes.ACTIVATE_ABILITY, card, lambda: random.randint(0, len(deck)))]
            draw_count = min(4, len(deck) + 1)
            for _ in range(draw_count):
                packet.append(TransferCard(lambda: deck.peek(), deck, hand, ActionTypes.ACTIVATE_ABILITY, card))
            return packet

        card.propose(generate_packet)
        return card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import AVGECardHPChange

        last_round = card.env.cache.get(card, JoshuaKou._LAST_ATK1_ROUND_KEY, None, True)
        if last_round is None or last_round < card.env.round_id - 1:
            card.propose(
                AVGECardHPChange(
                    lambda: card.player.opponent.get_active_card(),
                    40,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PIANO,
                    ActionTypes.ATK_1,
                    card,
                )
            )

        card.env.cache.set(card, JoshuaKou._LAST_ATK1_ROUND_KEY, card.env.round_id)
        return card.generate_response()
