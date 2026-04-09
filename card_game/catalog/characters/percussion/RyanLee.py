from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from typing import cast

class RyanLee(AVGECharacterCard):
    _ATK1_TARGET_KEY = "ryanlee_atk1_target"
    _ATK1_AMOUNT_KEY = "ryanlee_atk1_amount"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.PERCUSSION, 2, 1, 3)
        self.has_atk_1 = True
        self.has_atk_2 = True
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, AVGEEnergyTransfer, EmptyEvent

        bench = card.player.cardholders[Pile.BENCH]
        candidates = [c for c in bench if isinstance(c, AVGECharacterCard) and c.card_type == CardType.PERCUSSION]
        if len(candidates) == 0:
            return card.generate_response(data={MESSAGE_KEY:"No percussion on bench to give energy to!"})
        if len(card.player.energy) == 0:
            return card.generate_response(data={MESSAGE_KEY: "Play has no energy to give!"})

        missing = object()
        chosen = card.env.cache.get(card, RyanLee._ATK1_TARGET_KEY, missing, True)
        energy_amt = card.env.cache.get(card, RyanLee._ATK1_AMOUNT_KEY, missing, True)
        if chosen is missing or energy_amt is missing:
            def _target_valid(res) -> bool:
                if len(res) != 2:
                    return False
                sel = res[0]
                amt = int(res[1])
                return sel in candidates and amt <= len(card.player.energy) and amt <= 2 and amt > 0

            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [RyanLee._ATK1_TARGET_KEY, RyanLee._ATK1_AMOUNT_KEY],
                            InputType.DETERMINISTIC,
                            _target_valid,
                            ActionTypes.ATK_1,
                            card,
                            {
                                "query_label": "ryan-lee-atk1",
                                "targets": candidates,
                                "display": list(bench),
                                "maxamt": min(2, len(card.player.energy)),
                            },
                        )
                    ]
                },
            )
        assert isinstance(energy_amt, int)
        assert isinstance(chosen, AVGECharacterCard)
        def generate_packet() -> PacketType:
            if energy_amt <= 0 or len(card.player.energy) < energy_amt:
                return [
                    EmptyEvent(
                        ActionTypes.ATK_1,
                        card,
                        response_data = {MESSAGE_KEY: "Tried to run RyanLee ATK1 energy transfer, but energy state changed."}
                    )
                ]
            return [
                AVGEEnergyTransfer(token, card.player, chosen, ActionTypes.ATK_1, card)
                for token in list(card.player.energy)[:energy_amt]
            ]

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, RyanLee)))
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import TransferCard, AVGECardHPChange, EmptyEvent

        packet = []
        def gen_1() -> PacketType:
            return [AVGECardHPChange(
                card.player.opponent.get_active_card(),
                10,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.PERCUSSION,
                ActionTypes.ATK_2,
                card,
            )]
        packet += ([gen_1] * 4)
        if len(card.player.cardholders[Pile.DECK]) > 0:
            def gen_2() -> PacketType:
                return [
                    TransferCard(
                        card.player.cardholders[Pile.DECK].peek(),
                        card.player.cardholders[Pile.DECK],
                        card.player.cardholders[Pile.HAND],
                        ActionTypes.ATK_2,
                        card,
                    )
                ]
            packet.append(
                gen_2
            )
        else:
            packet.append(
                EmptyEvent(
                    ActionTypes.ATK_2,
                    card,
                    response_data={MESSAGE_KEY: "No more cards to draw from deck"}
                )
            )
        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_2, RyanLee)))

        return card.generate_response()
