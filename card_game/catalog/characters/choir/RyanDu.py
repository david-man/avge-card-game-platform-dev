from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from typing import cast


class RyanDu(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.CHOIR, 1, 2, 3)
        self.has_atk_1 = True
        self.atk_1_cost = 2
        self.has_atk_2 = True
        self.atk_2_cost = 3
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange
        from card_game.constants import ActionTypes

        def generate_packet() -> PacketType:
            opponent = card.player.opponent
            bench_count = len(card.player.cardholders[Pile.BENCH])
            damage = 30 + 10 * bench_count
            return [
                AVGECardHPChange(
                    opponent.get_active_card(),
                    damage,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.CHOIR,
                    ActionTypes.ATK_1,
                    card,
                )
            ]

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, RyanDu)))
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange, AVGEEnergyTransfer, EmptyEvent

        player = card.player
        opponent = player.opponent

        def generate_packet():
            packet = []
            if(len(card.energy) > 0):
                packet += [
                    AVGECardHPChange(
                        c,
                        40,
                        AVGEAttributeModifier.ADDITIVE,
                        CardType.ALL,
                        ActionTypes.ATK_2,
                        card,
                    ) for c in (player.cardholders[Pile.ACTIVE] + player.cardholders[Pile.BENCH])
                ]
                packet += [
                    AVGECardHPChange(
                        c,
                        10,
                        AVGEAttributeModifier.ADDITIVE,
                        CardType.ALL,
                        ActionTypes.ATK_2,
                        card,
                    ) for c in (opponent.cardholders[Pile.BENCH] + opponent.cardholders[Pile.ACTIVE])
                ]
                packet.append(
                    AVGEEnergyTransfer(
                        card.energy[0],
                        card,
                        player,
                        ActionTypes.ATK_2,
                        card,
                    )
                )
            else:
                packet.append(EmptyEvent(ActionTypes.ATK_2, card, response_data={MESSAGE_KEY: "Tried to run Ryan ATK2, but failed b/c energy dipped too low."}))
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_2, RyanDu)))
        return card.generate_response()
