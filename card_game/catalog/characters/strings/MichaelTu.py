from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class MichaelTu(AVGECharacterCard):
    _ATK1_TARGET = "michaeltu_atk1_target"
    _ACK = "michael_tu_ack"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 1, 1, 2)
        self.has_atk_1 = True
        self.atk_1_cost = 1
        self.has_atk_2 = True
        self.atk_2_cost = 2
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGEEnergyTransfer, InputEvent

        player = card.player
        if len(player.energy) <= 0:
            return card.generate_response(data={MESSAGE_KEY: "No energy to give!"})

        bench = player.cardholders[Pile.BENCH]
        if len(bench) == 0:
            return card.generate_response(data={MESSAGE_KEY: "No benched characters!"})

        chosen = card.env.cache.get(card, MichaelTu._ATK1_TARGET, None, True)
        if chosen is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            player,
                            [MichaelTu._ATK1_TARGET],
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            {
                                "query_label": "michael_tu_atk1",
                                "targets": bench,
                                "display": bench
                            },
                        )
                    ]
                },
            )

        card.propose(
            AVGEPacket([
                AVGEEnergyTransfer(player.energy[0], player, chosen, ActionTypes.ATK_1, card)
            ], AVGEEngineID(card, ActionTypes.ATK_1, MichaelTu))
        )

        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange, ReorderCardholder, TransferCard, EmptyEvent, InputEvent

        player = card.player
        deck = player.cardholders[Pile.DECK]
        hand = player.cardholders[Pile.HAND]

        first_char = None
        to_reveal : list[AVGECard] = []
        for c in deck:
            to_reveal.append(c)
            if isinstance(c, AVGECharacterCard):
                first_char = c
                break
        
        deck_order = list(deck.get_order())
        random.shuffle(deck_order)
        packet : PacketType = [ReorderCardholder(deck, deck_order, ActionTypes.ATK_2, card)]
        packet.append(EmptyEvent(
            ActionTypes.ATK_1,
            card,
            response_data={
                REVEAL_KEY: to_reveal
            }
        ))

        missing = object()
        chosen = card.env.cache.get(card, MichaelTu._ACK, missing, True)
        if chosen is missing:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            player,
                            [MichaelTu._ACK],
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            {
                                "query_label": "michael_tu_ack",
                                "targets": [first_char] if first_char is not None else [],
                                "display": to_reveal,
                                "allow_none": True
                            },
                        )
                    ]
                },
            )
        if first_char is None:
            card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_2, MichaelTu)))
            return card.generate_response()

        if first_char.card_type != CardType.STRING:
            def gen():
                ret : PacketType = []
                ret.append(TransferCard(first_char, first_char.cardholder, hand, ActionTypes.ATK_2, card))
                ret.append(
                    AVGECardHPChange(
                        card.player.opponent.get_active_card(),
                        30,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.STRING,
                        ActionTypes.ATK_2,
                        card,
                    )
                )
                return ret
            packet.append(gen)

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_2, MichaelTu)))

        return card.generate_response()
