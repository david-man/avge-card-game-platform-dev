from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import InputEvent, AVGECardHPChange, TransferCard


class LoangChiang(AVGECharacterCard):
    _BENCH_SWAP_KEY = "loang-bench-swap"

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.PERCUSSION, 2, 2, 3)
        self.atk_1_name = 'Stick Trick'
        self.atk_2_name = 'Excused Absence'

    def atk_1(self, card: AVGECharacterCard) -> Response:
        packet : PacketType = []
        def gen() -> PacketType:
            p: PacketType = []
            p.append(
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    20,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PERCUSSION,
                    ActionTypes.ATK_1,
                    None,
                    card,
                )
            )
            return p
        packet.append(gen)

        bench_holder = card.player.cardholders[Pile.BENCH]
        active_holder = card.player.cardholders[Pile.ACTIVE]
        bench_candidates = [c for c in bench_holder if isinstance(c, AVGECharacterCard)]
        if len(bench_candidates) == 0:
            card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, LoangChiang)))
            return self.generic_response(card, ActionTypes.ATK_1)

        missing = object()
        pick = card.env.cache.get(card, LoangChiang._BENCH_SWAP_KEY, missing, True)
        if pick is missing:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [LoangChiang._BENCH_SWAP_KEY],
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            CardSelectionQuery(
                                'Stick Trick: You may swap with a benched character for free',
                                bench_candidates,
                                list(bench_holder),
                                True,
                                False,
                            )
                        )
                    ]),
            )

        if isinstance(pick, AVGECharacterCard):
            packet.append(TransferCard(pick, bench_holder, active_holder, ActionTypes.ATK_1, card, None))
            packet.append(TransferCard(card, active_holder, bench_holder, ActionTypes.ATK_1, card, None))
        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, LoangChiang)))

        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard) -> Response:
        def gen() -> PacketType:
            packet: PacketType = []
            for c in card.player.get_cards_in_play():
                if not isinstance(c, AVGECharacterCard):
                    continue
                packet.append(
                    AVGECardHPChange(
                        c,
                        30,
                        AVGEAttributeModifier.ADDITIVE,
                        CardType.ALL,
                        ActionTypes.ATK_2,
                        None,
                        card,
                    )
                )
            return packet
        card.propose(
            AVGEPacket(
                [gen],
                AVGEEngineID(card, ActionTypes.ATK_2, LoangChiang),
            )
        )

        return self.generic_response(card, ActionTypes.ATK_2)
