from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class EvelynWu(AVGECharacterCard):
    _LAST_ATK1_ROUND_KEY = "evelyn_last_atk1_round"
    _CONSECUTIVE_USES = "evelyn_consecutive_atks"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.WOODWIND, 1, 1, 2)
        self.has_atk_1 = True
        self.has_atk_2 = True
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        last_round = card.env.cache.get(card, EvelynWu._LAST_ATK1_ROUND_KEY, None, True)
        atks_before = card.env.cache.get(card, EvelynWu._CONSECUTIVE_USES, 0, True)

        if last_round is None or card.env.round_id > last_round + 2:
            atks_before = 0
        assert isinstance(atks_before, int)
        damage_bonus = min(atks_before, 4) * 10
        total_damage = 10 + damage_bonus

        card.env.cache.set(card, EvelynWu._LAST_ATK1_ROUND_KEY, card.env.round_id)
        card.env.cache.set(card, EvelynWu._CONSECUTIVE_USES, atks_before + 1)

        def generate_packet() -> PacketType:
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                return [
                    AVGECardHPChange(
                        active,
                        total_damage,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.WOODWIND,
                        ActionTypes.ATK_1,
                        card,
                    )
                ]
            return []

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, EvelynWu)))
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        opponent_bench = card.player.opponent.cardholders[Pile.BENCH]
        total_damage = sum(max(0, bench_card.max_hp - bench_card.hp) for bench_card in opponent_bench if isinstance(bench_card, AVGECharacterCard))
        if total_damage <= 0:
            return card.generate_response()

        def generate_packet() -> PacketType:
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                return [
                    AVGECardHPChange(
                        active,
                        total_damage,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.WOODWIND,
                        ActionTypes.ATK_2,
                        card,
                    )
                ]
            return []

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_2, EvelynWu)))
        return card.generate_response()
