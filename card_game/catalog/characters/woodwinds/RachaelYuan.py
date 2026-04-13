from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class RachaelYuan(AVGECharacterCard):
    _LAST_ATK1_ROUND_KEY = "rachael_last_atk1_round"
    _CONSECUTIVE_USES = "rachael_consecutive_atks"
    _BENCH_SHUFFLE_KEY = "rachael_bench_shuffle"

    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.WOODWIND, 1, 1, 2)
        self.has_atk_1 = True
        self.has_atk_2 = True
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        last_round = card.env.cache.get(card, RachaelYuan._LAST_ATK1_ROUND_KEY, None, True)
        atks_before = card.env.cache.get(card, RachaelYuan._CONSECUTIVE_USES, 0, True)
        if last_round is None or card.env.round_id > last_round + 2:
            atks_before = 0
        assert isinstance(atks_before, int)
        total_damage = 10 + min(atks_before, 4) * 10
        card.env.cache.set(card, RachaelYuan._LAST_ATK1_ROUND_KEY, card.env.round_id)
        card.env.cache.set(card, RachaelYuan._CONSECUTIVE_USES, atks_before + 1)

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

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, RachaelYuan)))
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange, InputEvent, TransferCard

        opponent = card.player.opponent
        opponent_bench = opponent.cardholders[Pile.BENCH]
        opponent_deck = opponent.cardholders[Pile.DECK]

        def gen() -> PacketType:
            return [
            AVGECardHPChange(
                opponent.get_active_card(),
                30,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.WOODWIND,
                ActionTypes.ATK_2,
                card,
            )
        ]
        packet : PacketType =  [gen]

        if len(opponent_bench) >= 2:
            chosen_card = card.env.cache.get(card, RachaelYuan._BENCH_SHUFFLE_KEY, None, True)
            if chosen_card is None:
                return card.generate_response(
                    ResponseType.INTERRUPT,
                    {
                        INTERRUPT_KEY: [
                            InputEvent(
                                card.player,
                                [RachaelYuan._BENCH_SHUFFLE_KEY],
                                InputType.SELECTION,
                                lambda r: True,
                                ActionTypes.ATK_2,
                                card,
                                {
                                    LABEL_FLAG: "rachael_yuan_bench_shuffle",
                                    TARGETS_FLAG: list(opponent_bench),
                                    DISPLAY_FLAG: list(opponent_bench)
                                },
                            )
                        ]
                    },
                )
            assert chosen_card is not None
            packet.insert(0, 
                TransferCard(
                    chosen_card,
                    opponent_bench,
                    opponent_deck,
                    ActionTypes.ATK_2,
                    card,
                    random.randint(0, len(opponent_deck)),
                )
            )

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_2, RachaelYuan)))
        return card.generate_response()
