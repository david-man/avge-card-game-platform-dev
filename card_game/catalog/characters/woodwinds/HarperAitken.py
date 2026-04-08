from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class HarperAitken(AVGECharacterCard):
    _TARGET_1_SELECTION_KEY = "harperaitken_target_1_selection"
    _TARGET_2_SELECTION_KEY = "harperaitken_target_2_selection"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.WOODWIND, 2, 2, 3)
        self.has_atk_1 = True
        self.atk_1_cost = 2
        self.has_atk_2 = True
        self.atk_2_cost = 3
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange
        packet : PacketType = [
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    50,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_1,
                    card,
                ),
                AVGECardHPChange(
                    card,
                    10,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_1,
                    card,
                ),
            ]
        card.propose(
            AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, HarperAitken))
        )
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange, InputEvent

        opponent = card.player.opponent
        chars_in_play = opponent.get_cards_in_play()

        target_1 = card.env.cache.get(card, HarperAitken._TARGET_1_SELECTION_KEY, None, True)
        target_2 = card.env.cache.get(card, HarperAitken._TARGET_2_SELECTION_KEY, None, True)
        if target_1 is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [HarperAitken._TARGET_1_SELECTION_KEY, HarperAitken._TARGET_2_SELECTION_KEY],
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            {
                                "query_label": "harperaitken_wipeout",
                                "targets": chars_in_play,
                                "display": chars_in_play,
                                "allow_repeat": True
                            },
                        )
                    ]
                },
            )

        packet : PacketType = [
            AVGECardHPChange(
                target,
                80,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.WOODWIND,
                ActionTypes.ATK_2,
                card,
            )
            for target in [target_1, target_2, card]
        ]
        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_2, HarperAitken)))
        return card.generate_response()
