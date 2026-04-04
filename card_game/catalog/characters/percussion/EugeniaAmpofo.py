from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *
from card_game.internal_events import InputEvent, AVGECardHPChange, TransferCard, AVGEEnergyTransfer, EmptyEvent


class EugeniaAmpofo(AVGECharacterCard):
    _ATTACH_CHOICE_KEY = "eugenia_attach_choice"
    _ATTACH_USED_ROUND_KEY = "eugenia_attach_used_round"
    _BENCH_SWAP_KEY = "eugenia_bench_swap"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.PERCUSSION, 2, 2)
        self.has_atk_1 = True
        self.atk_1_cost = 2
        self.has_atk_2 = False
        self.has_passive = False
        self.has_active = True

    @staticmethod
    def can_play_active(card: AVGECharacterCard) -> bool:
        if card.cardholder.pile_type != Pile.ACTIVE:
            return False
        if len(card.player.energy) <= 0:
            return False
        if len(card.player.cardholders[Pile.BENCH]) == 0:
            return False
        used_round = card.env.cache.get(card, EugeniaAmpofo._ATTACH_USED_ROUND_KEY, None)
        return used_round != card.env.round_id

    @staticmethod
    def active(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        bench_chars = card.player.cardholders[Pile.BENCH]
        choice = card.env.cache.get(card, EugeniaAmpofo._ATTACH_CHOICE_KEY, None, True)
        if choice is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [EugeniaAmpofo._ATTACH_CHOICE_KEY],
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ACTIVATE_ABILITY,
                            card,
                            {
                                "query_label": "eugenia-active-ability",
                                "targets": list(bench_chars),
                            },
                        )
                    ]
                },
            )

        target_card = choice

        def generate_packet():
            if len(card.player.energy) <= 0:
                return [
                    EmptyEvent(
                        "Tried to play Eugenia active, but no player energy was available.",
                        ActionTypes.ACTIVATE_ABILITY,
                        card,
                    )
                ]
            return [
                AVGEEnergyTransfer(
                    card.player.energy[0],
                    card.player,
                    target_card,
                    ActionTypes.ACTIVATE_ABILITY,
                    card,
                )
            ]

        card.env.cache.set(card, EugeniaAmpofo._ATTACH_USED_ROUND_KEY, card.env.round_id)
        card.propose(generate_packet)
        return card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        packet = [
            AVGECardHPChange(
                lambda: card.player.opponent.get_active_card(),
                20,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.PERCUSSION,
                ActionTypes.ATK_1,
                card,
            )
        ]

        bench_holder = card.player.cardholders[Pile.BENCH]
        active_holder = card.player.cardholders[Pile.ACTIVE]
        perc_candidates = [c for c in bench_holder if c.card_type == CardType.PERCUSSION]
        if len(perc_candidates) == 0:
            card.propose(packet)
            return card.generate_response()

        missing = object()
        pick = card.env.cache.get(card, EugeniaAmpofo._BENCH_SWAP_KEY, missing, True)
        if pick is missing:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [EugeniaAmpofo._BENCH_SWAP_KEY],
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            {
                                "query_label": "EugeniaAmpofo-benched-percussion-swap",
                                "targets": perc_candidates,
                                "allow_none": True,
                            },
                        )
                    ]
                },
            )

        if pick is not None:
            packet.append(TransferCard(pick, bench_holder, active_holder, ActionTypes.ATK_1, card))
            packet.append(TransferCard(card, active_holder, bench_holder, ActionTypes.ATK_1, card))
        card.propose(packet)

        return card.generate_response()
