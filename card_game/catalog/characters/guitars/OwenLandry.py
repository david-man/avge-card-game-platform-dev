from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import ActionTypes


class OwenLandry(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.GUITAR, 2, 2, 3)
        self.has_atk_1 = True
        self.has_atk_2 = True
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        def generate_packet() -> PacketType:
            packet : PacketType  = []
            packet = [
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    50,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.GUITAR,
                    ActionTypes.ATK_1,
                    card,
                )
            ]
            for c in card.player.cardholders[Pile.BENCH]:
                assert isinstance(c, AVGECharacterCard)
                if c.card_type == CardType.GUITAR:
                    packet.append(
                        AVGECardHPChange(
                            c,
                            10,
                            AVGEAttributeModifier.SUBSTRACTIVE,
                            CardType.GUITAR,
                            ActionTypes.ATK_1,
                            card,
                        )
                    )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, OwenLandry)))
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange, AVGEEnergyTransfer

        def generate_packet() -> PacketType:
            packet = []
            for token in list(card.energy):
                packet.append(AVGEEnergyTransfer(token, card, card.player, ActionTypes.ATK_2, card))

            opp = card.player.opponent
            for c in opp.get_cards_in_play():
                packet.append(
                    AVGECardHPChange(
                        c,
                        50,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.GUITAR,
                        ActionTypes.ATK_2,
                        card,
                    )
                )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_2, OwenLandry)))
        return card.generate_response()
