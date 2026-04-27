from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class RyanDu(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.CHOIR, 2, 1, 2)
        self.atk_1_name = 'Tabemono King'
        self.atk_2_name = 'Chorus'

    def atk_1(self, card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange, AVGEEnergyTransfer

        def generate_packet() -> PacketType:
            packet: PacketType = []
            current_energy = len(card.energy)
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        30 * current_energy,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.CHOIR,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )

            for token in list(card.energy):
                packet.append(
                    AVGEEnergyTransfer(
                        token,
                        card,
                        card.env,
                        ActionTypes.ATK_1,
                        card,
                        None,
                    )
                )

            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, RyanDu)))
        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        def generate_packet():
            packet: PacketType = []
            bench_count = len(card.player.cardholders[Pile.BENCH])
            damage = 20 + 10 * bench_count
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        damage,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.CHOIR,
                        ActionTypes.ATK_2,
                        None,
                        card,
                    )
                )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_2, RyanDu)))
        return self.generic_response(card, ActionTypes.ATK_2)
