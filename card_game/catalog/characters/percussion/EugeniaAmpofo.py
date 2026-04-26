from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import InputEvent, TransferCard, AVGEEnergyTransfer, AVGECardHPChange, PlayCharacterCard


class EugeniaAmpofo(AVGECharacterCard):
    _ATTACH_CHOICE_KEY = "eugenia_attach_choice"
    _BENCH_SWAP_KEY = "eugenia_bench_swap"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.PERCUSSION, 2, 2)
        self.atk_1_name = 'Stick Trick'
        self.active_name = 'Fermentation'

    def can_play_active(self) -> bool:
        if self.env.player_turn != self.player:
            return False
        if self.cardholder is None or self.cardholder.pile_type != Pile.ACTIVE:
            return False
        if len(self.player.energy) <= 0:
            return False
        if len(self.player.cardholders[Pile.BENCH]) == 0:
            return False
        _, already_used_idx = self.env.check_history(
            self.env.round_id,
            PlayCharacterCard,
            {
                'card': self,
                'card_action': ActionTypes.ACTIVATE_ABILITY,
                'caller': self,
            },
        )
        return already_used_idx == -1

    def active(self) -> Response:
        bench_chars = self.player.cardholders[Pile.BENCH]
        missing = object()
        choice = self.env.cache.get(self, EugeniaAmpofo._ATTACH_CHOICE_KEY, missing, True)
        if choice is missing:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            self.player,
                            [EugeniaAmpofo._ATTACH_CHOICE_KEY],
                            lambda r: True,
                            ActionTypes.ACTIVATE_ABILITY,
                            self,
                            CardSelectionQuery(
                                'Fermentation: Attach an extra (X) to one benched character',
                                list(bench_chars),
                                list(bench_chars),
                                False,
                                False,
                            )
                        )
                    ]),
            )
        if not isinstance(choice, AVGECharacterCard):
            return Response(ResponseType.ACCEPT, Data())

        def generate_packet() -> PacketType:
            packet: PacketType = []
            if len(self.player.energy) <= 0:
                return packet
            packet.append(
                AVGEEnergyTransfer(
                    self.player.energy[0],
                    self.env,
                    choice,
                    ActionTypes.ACTIVATE_ABILITY,
                    self,
                    None,
                )
            )
            return packet

        self.propose(AVGEPacket([generate_packet], AVGEEngineID(self, ActionTypes.ACTIVATE_ABILITY, EugeniaAmpofo)))
        return self.generic_response(self, ActionTypes.ACTIVATE_ABILITY)

    def atk_1(self, card: AVGECharacterCard) -> Response:
        packet : PacketType = []
        def generate() -> PacketType:
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
        packet.append(generate)

        bench_holder = card.player.cardholders[Pile.BENCH]
        active_holder = card.player.cardholders[Pile.ACTIVE]
        bench_candidates = [c for c in bench_holder if isinstance(c, AVGECharacterCard)]
        if len(bench_candidates) == 0:
            card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, EugeniaAmpofo)))
            return self.generic_response(card, ActionTypes.ATK_1)
        missing = object()
        pick = card.env.cache.get(card, EugeniaAmpofo._BENCH_SWAP_KEY, missing, True)
        if pick is missing:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [EugeniaAmpofo._BENCH_SWAP_KEY],
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
        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, EugeniaAmpofo)))

        return self.generic_response(card, ActionTypes.ATK_1)
