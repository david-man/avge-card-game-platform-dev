from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import ActionTypes


class OwenLandry(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.GUITAR, 2, 2, 3)
        self.atk_1_name = 'Feedback Loop'
        self.atk_2_name = 'Domain Expansion'

    def atk_1(self, card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        def generate_packet() -> PacketType:
            packet: PacketType = []
            packet.append(
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    50,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.GUITAR,
                    ActionTypes.ATK_1,
                    None,
                    card,
                )
            )
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
                            None,
                            card,
                        )
                    )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, OwenLandry)))
        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange, AVGEEnergyTransfer

        def generate_packet() -> PacketType:
            packet: PacketType = []
            for token in list(card.energy):
                packet.append(AVGEEnergyTransfer(token, card, card.env, ActionTypes.ATK_2, card, None))

            opp = card.player.opponent
            for c in opp.get_cards_in_play():
                packet.append(
                    AVGECardHPChange(
                        c,
                        50,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.GUITAR,
                        ActionTypes.ATK_2,
                        None,
                        card,
                    )
                )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_2, OwenLandry)))
        return self.generic_response(card, ActionTypes.ATK_2)
