from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class JoshuaKou(AVGECharacterCard):
    _LAST_ATK1_ROUND_KEY = "joshuakou_atk1_last_round"
    _PASSIVE_DRAW_CHOICE_KEY = "joshuakou_passive_draw_choice"

    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.PIANO, 1, 1)
        self.has_atk_1 = True
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, TransferCard

        hand = card.player.cardholders[Pile.HAND]
        deck = card.player.cardholders[Pile.DECK]

        if(len(hand) >= 4 or len(deck) == 0):
            return card.generate_response()

        draw_choice = card.env.cache.get(card, JoshuaKou._PASSIVE_DRAW_CHOICE_KEY, None, True)
        if(draw_choice is None):
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [JoshuaKou._PASSIVE_DRAW_CHOICE_KEY],
                            InputType.BINARY,
                            lambda r: True,
                            ActionTypes.PASSIVE,
                            card,
                            {LABEL_FLAG: "joshuakou_passive_draw_until_four"},
                        )
                    ]
                },
            )

        if(not draw_choice):
            return card.generate_response()

        def draw_until_four() -> PacketType:
            current_hand = card.player.cardholders[Pile.HAND]
            current_deck = card.player.cardholders[Pile.DECK]
            def gen() -> PacketType:
                if(len(current_deck) == 0 or len(current_hand) >= 4):
                    return []
                else:
                    return [TransferCard(
                        current_deck.peek(),
                        current_deck,
                        current_hand,
                        ActionTypes.PASSIVE,
                        card,
                    )]
            return [gen] * 4

        card.propose(
            AVGEPacket([
                draw_until_four
            ], AVGEEngineID(card, ActionTypes.PASSIVE, JoshuaKou))
        )
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
