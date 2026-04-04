from __future__ import annotations

import random

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *


class MichaelTu(AVGECharacterCard):
    _ATK1_TARGET = "michaeltu_atk1_target"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 1, 1, 2)
        self.has_atk_1 = True
        self.atk_1_cost = 1
        self.has_atk_2 = True
        self.atk_2_cost = 2
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import AVGEEnergyTransfer, InputEvent

        player = card.player
        if len(player.energy) <= 0:
            return card.generate_response()

        bench_list = [c for c in player.cardholders[Pile.BENCH]]
        if len(bench_list) == 0:
            return card.generate_response()

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
                                "query_label": "michael_tu_440hz",
                                "targets": bench_list,
                            },
                        )
                    ]
                },
            )

        card.propose(AVGEEnergyTransfer(player.energy[0], player, chosen, ActionTypes.ATK_1, card))
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import AVGECardHPChange, ReorderCardholder, TransferCard

        player = card.player
        deck = player.cardholders[Pile.DECK]
        hand = player.cardholders[Pile.HAND]

        first_char = None
        for c in deck:
            if isinstance(c, AVGECharacterCard):
                first_char = c
                break
                    
        deck_order = list(deck.get_order())
        random.shuffle(deck_order)
        packet = [ReorderCardholder(deck, deck_order, ActionTypes.ATK_2, card)]

        if first_char is None:
            card.propose(packet)
            return card.generate_response()

        if first_char.card_type != CardType.STRING:
            packet.append(TransferCard(first_char, deck, hand, ActionTypes.ATK_2, card))
            packet.append(
                AVGECardHPChange(
                    lambda: card.player.opponent.get_active_card(),
                    30,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.STRING,
                    ActionTypes.ATK_2,
                    card,
                )
            )

        card.propose(packet)

        return card.generate_response()
