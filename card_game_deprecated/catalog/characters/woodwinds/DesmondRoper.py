from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import AVGECardHPChange, PlayCharacterCard, TransferCard


class DesmondRoper(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.WOODWIND, 2, 1, 3)
        self.atk_1_name = 'Circular Breathing'
        self.atk_2_name = 'Speedrun Central'

    def atk_1(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
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
        damage = 10 + bonus

        def gen() -> PacketType:
            packet: PacketType = []
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        damage,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.WOODWIND,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )
            return packet

        card.propose(AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_1, DesmondRoper)))
        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        _, played_to_active_idx = card.env.check_history(
            card.env.round_id,
            TransferCard,
            {
                'card': card,
                'pile_to': card.player.cardholders[Pile.ACTIVE],
            },
        )
        played_to_active_this_turn = played_to_active_idx != -1

        damage = 100 if played_to_active_this_turn else 40

        def generate_packet() -> PacketType:
            packet: PacketType = []
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        damage,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.WOODWIND,
                        ActionTypes.ATK_2,
                        None,
                        card,
                    )
                )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_2, DesmondRoper)))
        return self.generic_response(card, ActionTypes.ATK_2)
