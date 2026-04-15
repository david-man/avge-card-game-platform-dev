from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import InputEvent, TransferCard, AVGEEnergyTransfer, EmptyEvent, AVGECardHPChange


class EugeniaAmpofo(AVGECharacterCard):
    _ATTACH_CHOICE_KEY = "eugenia_attach_choice"
    _ATTACH_USED_ROUND_KEY = "eugenia_attach_used_round"
    _BENCH_SWAP_KEY = "eugenia_bench_swap"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.PERCUSSION, 2, 2)
        self.has_atk_1 = True
        self.has_atk_2 = False
        self.has_passive = False
        self.has_active = True

    @staticmethod
    def can_play_active(card: AVGECharacterCard) -> bool:
        if card.env.player_turn != card.player:
            return False
        if card.cardholder.pile_type != Pile.ACTIVE:
            return False
        if len(card.player.energy) <= 0:
            return False
        if len(card.player.cardholders[Pile.BENCH]) == 0:
            return False
        used_round = card.env.cache.get(card, EugeniaAmpofo._ATTACH_USED_ROUND_KEY, None)
        return used_round != card.env.round_id

    @staticmethod
    def active(card: AVGECharacterCard) -> Response:
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
                                LABEL_FLAG: "eugenia_ampofo_active_ability",
                                TARGETS_FLAG: list(bench_chars),
                                DISPLAY_FLAG: list(bench_chars)
                            },
                        )
                    ]
                },
            )
        target_card = choice

        def generate_packet() -> PacketType:
            if len(card.player.energy) <= 0:
                return [
                    EmptyEvent(
                        ActionTypes.ACTIVATE_ABILITY,
                        card,
                        response_data = {MESSAGE_KEY: "Tried to play Eugenia active, but no player energy was available."}
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
        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ACTIVATE_ABILITY, EugeniaAmpofo)))
        return card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        packet : PacketType = []
        def generate() -> PacketType:
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
        packet.append(generate)

        bench_holder = card.player.cardholders[Pile.BENCH]
        active_holder = card.player.cardholders[Pile.ACTIVE]
        perc_candidates = [c for c in bench_holder if isinstance(c, AVGECharacterCard) and c.card_type == CardType.PERCUSSION]
        if len(bench_holder) == 0:
            card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, EugeniaAmpofo)))
            return card.generate_response(data = {MESSAGE_KEY: "No bench characters to swap with! Skipping past bench swap."})
        missing = object()
        pick = card.env.cache.get(card, EugeniaAmpofo._BENCH_SWAP_KEY, None, True)
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
                                LABEL_FLAG: "eugenia_ampofo_benched_percussion_swap",
                                TARGETS_FLAG: perc_candidates,
                                DISPLAY_FLAG: list(bench_holder),
                                ALLOW_NONE: True,
                            },
                        )
                    ]
                },
            )
        if pick is not None:
            packet.append(TransferCard(pick, bench_holder, active_holder, ActionTypes.ATK_1, card))
            packet.append(TransferCard(card, active_holder, bench_holder, ActionTypes.ATK_1, card))
        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, EugeniaAmpofo)))

        return card.generate_response()
