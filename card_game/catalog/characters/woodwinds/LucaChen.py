from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class LucaChen(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.WOODWIND, 1, 2, 2)
        self.has_atk_1 = True
        self.has_atk_2 = True
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange
        def gen() -> PacketType:
            return [
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    30,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_1,
                    card,
                ),
                AVGECardHPChange(
                    card,
                    20,
                    AVGEAttributeModifier.ADDITIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_1,
                    card,
                ),
            ]
        card.propose(
            AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_1, LucaChen))
        )
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        all_characters = card.player.get_cards_in_play() + card.player.opponent.get_cards_in_play()
        other_ww_count = sum(
            1
            for character in all_characters
            if isinstance(character, AVGECharacterCard) and character != card and character.card_type == CardType.WOODWIND
        )

        if other_ww_count == 0:
            def gen() -> PacketType:
                return [
                    AVGECardHPChange(
                        card.player.opponent.get_active_card(),
                        70,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.WOODWIND,
                        ActionTypes.ATK_2,
                        card,
                    )
                ]
            card.propose(
                AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_2, LucaChen))
            )

        return card.generate_response()
