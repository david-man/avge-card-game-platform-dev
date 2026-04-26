from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from typing import cast


class RyanDu(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.CHOIR, 1, 2, 3)
        self.atk_1_name = 'Chorus'
        self.atk_2_name = 'Tabemono King'

    def atk_1(self, card: AVGECharacterCard) -> Response:
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
                    None,
                    card,
                )
            ]

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, RyanDu)))
        return Response(ResponseType.CORE, Notify(f"{str(card)} used Chorus!", all_players, default_timeout))

    def atk_2(self, card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange, AVGEEnergyTransfer, EmptyEvent

        player = card.player
        opponent = player.opponent

        def generate_packet():
            packet = []
            packet += [
                AVGECardHPChange(
                    c,
                    40,
                    AVGEAttributeModifier.ADDITIVE,
                    CardType.ALL,
                    ActionTypes.ATK_2,
                    None,
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
                    None,
                    card,
                ) for c in (opponent.cardholders[Pile.BENCH] + opponent.cardholders[Pile.ACTIVE])
            ]
            if(len(card.energy) > 0):
                
                packet.append(
                    AVGEEnergyTransfer(
                        card.energy[0],
                        card,
                        card.env,
                        ActionTypes.ATK_2,
                        card,
                        None,
                    )
                )
            else:
                packet.append(EmptyEvent(ActionTypes.ATK_2, card, ResponseType.CORE, Data()))
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_2, RyanDu)))
        return Response(ResponseType.CORE, Notify(f"{str(card)} used Tabemono King!", all_players, default_timeout))
