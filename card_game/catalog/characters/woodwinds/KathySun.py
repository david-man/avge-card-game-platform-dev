from __future__ import annotations

import random

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class KathySun(AVGECharacterCard):
    _OPPONENT_SHUFFLE_KEY_1 = "kathysun_opponent_shuffle_selection_1"
    _OPPONENT_SHUFFLE_KEY_2 = "kathysun_opponent_shuffle_selection_2"
    _D6_ROLL_KEY = "kathysun_runtime_d6_roll"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.WOODWIND, 1, 1, 3)
        self.has_atk_1 = True
        self.atk_1_cost = 1
        self.has_atk_2 = True
        self.atk_2_cost = 3
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, TransferCardCreator

        opponent = card.player.opponent
        opponent_hand = opponent.cardholders[Pile.HAND]
        opponent_deck = opponent.cardholders[Pile.DECK]

        if len(opponent_hand) <= 2:
            packet = [] + [
                TransferCardCreator(
                    hand_card,
                    opponent_hand,
                    opponent_deck,
                    ActionTypes.ATK_1,
                    card,
                    lambda: random.randint(0, len(opponent_deck)),
                )
                for hand_card in list(opponent_hand)
            ]
            card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, KathySun)))
            return card.generate_response()

        chosen_for_shuffle_1 = card.env.cache.get(card, KathySun._OPPONENT_SHUFFLE_KEY_1, None, True)
        chosen_for_shuffle_2 = card.env.cache.get(card, KathySun._OPPONENT_SHUFFLE_KEY_2, None, True)
        if chosen_for_shuffle_1 is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            opponent,
                            [KathySun._OPPONENT_SHUFFLE_KEY_1, KathySun._OPPONENT_SHUFFLE_KEY_2],
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            {
                                "query_label": "kathy_sun_opponent_shuffle",
                                "targets": list(opponent_hand),
                            },
                        )
                    ]
                },
            )
        assert chosen_for_shuffle_2 is not None
        card.propose(
            AVGEPacket([
                TransferCardCreator(
                    chosen_for_shuffle_1,
                    opponent_hand,
                    opponent_deck,
                    ActionTypes.ATK_1,
                    card,
                    lambda: random.randint(0, len(opponent_deck)),
                ),
                TransferCardCreator(
                    chosen_for_shuffle_2,
                    opponent_hand,
                    opponent_deck,
                    ActionTypes.ATK_1,
                    card,
                    lambda: random.randint(0, len(opponent_deck)),
                ),
            ], AVGEEngineID(card, ActionTypes.ATK_1, KathySun))
        )
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChangeCreator, InputEvent

        roll = card.env.cache.get(card, KathySun._D6_ROLL_KEY, None, True)
        if roll is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [KathySun._D6_ROLL_KEY],
                            InputType.D6,
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            {"query_label": "kathy_sun_d6"},
                        )
                    ]
                },
            )

        damage = 30 + 10 * int(roll)
        card.propose(
            AVGEPacket([
                AVGECardHPChangeCreator(
                    lambda: card.player.opponent.get_active_card(),
                    damage,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_2,
                    card,
                )
            ], AVGEEngineID(card, ActionTypes.ATK_2, KathySun))
        )
        return card.generate_response()
