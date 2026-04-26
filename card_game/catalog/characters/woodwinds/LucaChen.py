from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import AVGECardHPChange

class LucaChen(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.WOODWIND, 1, 2, 3)
        self.atk_1_name = 'Sparkling Run'
        self.atk_2_name = 'Piccolo Solo'

    def atk_1(self, card: AVGECharacterCard) -> Response:
        def gen() -> PacketType:
            packet: PacketType = []
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        30,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.WOODWIND,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )
            packet.append(
                AVGECardHPChange(
                    card,
                    20,
                    AVGEAttributeModifier.ADDITIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_1,
                    None,
                    card,
                )
            )
            return packet

        card.propose(
            AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_1, LucaChen))
        )
        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard) -> Response:
        all_characters = card.player.get_cards_in_play() + card.player.opponent.get_cards_in_play()
        other_ww_count = sum(
            1
            for character in all_characters
            if isinstance(character, AVGECharacterCard) and character != card and character.card_type == CardType.WOODWIND
        )
        total_damage = 40 + (50 if other_ww_count == 0 else 0)

        def gen() -> PacketType:
            packet: PacketType = []
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        total_damage,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.WOODWIND,
                        ActionTypes.ATK_2,
                        None,
                        card,
                    )
            )
            return packet

        card.propose(
            AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_2, LucaChen))
        )

        return self.generic_response(card, ActionTypes.ATK_2)
