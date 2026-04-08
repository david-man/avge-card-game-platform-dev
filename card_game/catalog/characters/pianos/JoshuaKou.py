from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

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
        from card_game.internal_events import TransferCard, EmptyEvent

        hand = card.player.cardholders[Pile.HAND]
        deck = card.player.cardholders[Pile.DECK]

        def generate_packet() -> PacketType:
            if card not in hand:
                return [
                    EmptyEvent(
                        ActionTypes.ACTIVATE_ABILITY,
                        card,
                        response_data={MESSAGE_KEY: "JoshuaKou active failed: card not in hand."},
                    )
                ]
            
            packet: PacketType = [
                EmptyEvent(
                    ActionTypes.ACTIVATE_ABILITY,
                    card,
                    response_data={
                        REVEAL_KEY: [card]
                    }
                ),
                TransferCard(
                    card,
                    hand,
                    deck,
                    ActionTypes.ACTIVATE_ABILITY,
                    card,
                    random.randint(0, len(deck)),
                )
            ]
            def draw_top() -> PacketType:
                if len(deck) == 0:
                    return []
                return [
                    TransferCard(
                        deck.peek(),
                        deck,
                        hand,
                        ActionTypes.ACTIVATE_ABILITY,
                        card,
                    )
                ]

            for _ in range(4):
                packet.append(draw_top)
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ACTIVATE_ABILITY, JoshuaKou)))
        return card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        last_round = card.env.cache.get(card, JoshuaKou._LAST_ATK1_ROUND_KEY, None, True)
        if last_round is None or last_round < card.env.round_id - 1:
            def generate_packet() -> PacketType:
                active = card.player.opponent.get_active_card()
                return [
                    AVGECardHPChange(
                        active,
                        40,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.PIANO,
                        ActionTypes.ATK_1,
                        card,
                    )
                ]

            card.propose(
                AVGEPacket([
                    generate_packet
                ], AVGEEngineID(card, ActionTypes.ATK_1, JoshuaKou))
            )

        card.env.cache.set(card, JoshuaKou._LAST_ATK1_ROUND_KEY, card.env.round_id)
        return card.generate_response()
