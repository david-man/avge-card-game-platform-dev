from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *


class KevinYang(AVGECharacterCard):
    _D6_KEY = "kevin_d6_roll"
    _D6_KEYS_4 = [f"kevin_d6_roll_{i}" for i in range(4)]

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.PERCUSSION, 2, 2, 3)
        self.has_atk_1 = True
        self.atk_1_cost = 2
        self.has_atk_2 = True
        self.atk_2_cost = 3
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import InputEvent, AVGECardHPChange

        roll = card.env.cache.get(card, KevinYang._D6_KEY, None, True)
        if roll is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [KevinYang._D6_KEY],
                            InputType.D6,
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            {"query_label": "kevin-yang-d6"},
                        )
                    ]
                },
            )

        val = int(roll)
        if val <= 4:
            card.propose(
                AVGECardHPChange(
                    lambda: card.player.opponent.get_active_card(),
                    70,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PERCUSSION,
                    ActionTypes.ATK_1,
                    card,
                )
            )

        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import InputEvent, AVGECardHPChange

        rolls = [card.env.cache.get(card, key, None, True) for key in KevinYang._D6_KEYS_4]
        if rolls[0] is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            KevinYang._D6_KEYS_4,
                            InputType.D6,
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            {"query_label": "kevin-yang-4d6"},
                        )
                    ]
                },
            )

        lowest = min(int(v) for v in rolls)
        damage = 40 * lowest

        card.propose(
            AVGECardHPChange(
                lambda: card.player.opponent.get_active_card(),
                damage,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.PERCUSSION,
                ActionTypes.ATK_2,
                card,
            )
        )

        return card.generate_response()
