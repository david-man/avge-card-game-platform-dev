from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes


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
    def atk_1(card: AVGECharacterCard) -> Response:
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
                            {"query_label": "kevin_yang_d6"},
                        )
                    ]
                },
            )

        val = int(roll)
        if val <= 4:
            def gen() -> PacketType:
                return [
                    AVGECardHPChange(
                        card.player.opponent.get_active_card(),
                        70,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.PERCUSSION,
                        ActionTypes.ATK_1,
                        card,
                    )
                ]
            card.propose(
                AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_1, KevinYang))
            )

        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
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
                            {"query_label": "kevin_yang_4d6"},
                        )
                    ]
                },
            )

        lowest = min(int(v) for v in rolls if v is not None)
        damage = 40 * lowest
        def gen() -> PacketType:
            return [
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    damage,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PERCUSSION,
                    ActionTypes.ATK_2,
                    card,
                )
            ]
        card.propose(
            AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_2, KevinYang))
        )

        return card.generate_response()
