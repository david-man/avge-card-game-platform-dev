from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import InputEvent, AVGECardHPChange, TransferCard


class LoangChiang(AVGECharacterCard):
    _BENCH_SWAP_KEY = "loang-bench-swap"

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.PERCUSSION, 2, 2, 3)
        self.has_atk_1 = True
        self.atk_1_cost = 2
        self.has_atk_2 = True
        self.atk_2_cost = 3
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        packet : PacketType = []
        def gen() -> PacketType:
            return [
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    20,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PERCUSSION,
                    ActionTypes.ATK_1,
                    card,
                )
            ]
        packet += [gen]

        bench_holder = card.player.cardholders[Pile.BENCH]
        active_holder = card.player.cardholders[Pile.ACTIVE]
        perc_candidates = [c for c in bench_holder if isinstance(c, AVGECharacterCard) and c.card_type == CardType.PERCUSSION]
        if len(perc_candidates) == 0:
            card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, LoangChiang)))
            return card.generate_response()

        missing = object()
        pick = card.env.cache.get(card, LoangChiang._BENCH_SWAP_KEY, missing, True)
        if pick is missing:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [LoangChiang._BENCH_SWAP_KEY],
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            {
                                "query_label": "loang_chiang_benched_percussion_swap",
                                "targets": perc_candidates,
                                "display": list(bench_holder),
                                "allow_none": True,
                            },
                        )
                    ]
                },
            )

        if pick is not None:
            packet.append(TransferCard(pick, bench_holder, active_holder, ActionTypes.ATK_1, card))
            packet.append(TransferCard(card, active_holder, bench_holder, ActionTypes.ATK_1, card))
        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, LoangChiang)))

        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        def gen() -> PacketType:
            return [
                    AVGECardHPChange(
                        c,
                        30,
                        AVGEAttributeModifier.ADDITIVE,
                        CardType.ALL,
                        ActionTypes.ATK_2,
                        card,
                    ) for c in card.player.get_cards_in_play()
                ]
        card.propose(
            AVGEPacket(
                [gen],
                AVGEEngineID(card, ActionTypes.ATK_2, LoangChiang),
            )
        )

        return card.generate_response()
