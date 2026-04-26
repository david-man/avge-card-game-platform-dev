from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import AVGECardHPChange, PlayCharacterCard


class EvelynWu(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.WOODWIND, 1, 1, 2)
        self.atk_1_name = 'Circular Breathing'
        self.atk_2_name = 'Small Ensemble Lord'

    def atk_1(self, card: AVGECharacterCard) -> Response:
        streak = 0
        turn = card.player.get_last_turn()
        while streak < 4 and turn >= 0:
            _, used_last_turn_idx = card.env.check_history(
                turn,
                PlayCharacterCard,
                {
                    'card': card,
                    'card_action': ActionTypes.ATK_1,
                    'caller': card,
                },
            )
            if used_last_turn_idx == -1:
                break
            streak += 1
            turn -= 2

        bonus = min(40, 10 * streak)
        total_damage = 10 + bonus

        def generate_packet() -> PacketType:
            packet: PacketType = []
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        total_damage,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.WOODWIND,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, EvelynWu)))
        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard) -> Response:
        def generate_packet() -> PacketType:
            packet: PacketType = []
            opponent = card.player.opponent

            transfer_total = 0
            for bench_card in opponent.cardholders[Pile.BENCH]:
                if not isinstance(bench_card, AVGECharacterCard):
                    continue
                existing_damage = max(0, bench_card.max_hp - bench_card.hp)
                if existing_damage <= 0:
                    continue

                transfer_total += existing_damage
                packet.append(
                    AVGECardHPChange(
                        bench_card,
                        existing_damage,
                        AVGEAttributeModifier.ADDITIVE,
                        CardType.ALL,
                        ActionTypes.ATK_2,
                        None,
                        card,
                    )
                )

            active = opponent.get_active_card()
            if transfer_total > 0 and isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        transfer_total,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.WOODWIND,
                        ActionTypes.ATK_2,
                        None,
                        card,
                    )
                )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_2, EvelynWu)))
        return self.generic_response(card, ActionTypes.ATK_2)
