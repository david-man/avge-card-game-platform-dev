from __future__ import annotations

import random

from card_game.avge_abstracts.AVGECards import *
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
    def active(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import TransferCardCreator, EmptyEvent

        hand = card.player.cardholders[Pile.HAND]
        deck = card.player.cardholders[Pile.DECK]

        def generate_packet():
            if card not in hand:
                return AVGEPacket([EmptyEvent("JoshuaKou active failed: card not in hand.", ActionTypes.ACTIVATE_ABILITY, card)], AVGEEngineID(card, ActionTypes.ACTIVATE_ABILITY, JoshuaKou))
            packet = [
                TransferCardCreator(
                    card,
                    hand,
                    deck,
                    ActionTypes.ACTIVATE_ABILITY,
                    card,
                    lambda: random.randint(0, len(deck)),
                )
            ]
            draw_count = min(4, len(deck) + 1)
            for _ in range(draw_count):
                packet.append(TransferCardCreator(lambda: deck.peek(), deck, hand, ActionTypes.ACTIVATE_ABILITY, card))
            return AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ACTIVATE_ABILITY, JoshuaKou))

        card.propose(generate_packet())
        return card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChangeCreator

        last_round = card.env.cache.get(card, JoshuaKou._LAST_ATK1_ROUND_KEY, None, True)
        if last_round is None or last_round < card.env.round_id - 1:
            card.propose(
                AVGEPacket([
                    AVGECardHPChangeCreator(
                        lambda: card.player.opponent.get_active_card(),
                        40,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.PIANO,
                        ActionTypes.ATK_1,
                        card,
                    )
                ], AVGEEngineID(card, ActionTypes.ATK_1, JoshuaKou))
            )

        card.env.cache.set(card, JoshuaKou._LAST_ATK1_ROUND_KEY, card.env.round_id)
        return card.generate_response()
