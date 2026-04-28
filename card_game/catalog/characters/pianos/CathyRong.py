from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import InputEvent, AVGECardHPChange, AVGEEnergyTransfer

class CathyRong(AVGECharacterCard):
    _ENERGY_TARGET_KEY = "cathy_energy_target"

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.PIANO, 2, 2, 3)
        self.atk_1_name = 'Racket Smash'
        self.atk_2_name = 'Four Hands'

    def atk_1(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        opponent = card.player.opponent
        bench_candidates = [c for c in opponent.cardholders[Pile.BENCH] if isinstance(c, AVGECharacterCard) and len(c.energy) >= 1]

        missing = object()
        chosen = card.env.cache.get(card, CathyRong._ENERGY_TARGET_KEY, missing, True)
        if len(bench_candidates) > 0 and chosen is missing:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [CathyRong._ENERGY_TARGET_KEY],
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            CardSelectionQuery(
                                'Racket Smash: Choose an opposing benched character to discard 1 energy from',
                                bench_candidates,
                                list(opponent.cardholders[Pile.BENCH]),
                                False,
                                False,
                            )
                        )
                    ]),
            )

        def gen_damage() -> PacketType:
            packet: PacketType = []
            packet.append(
                AVGECardHPChange(
                    opponent.get_active_card(),
                    20,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PIANO,
                    ActionTypes.ATK_1,
                    None,
                    card,
                )
            )
            return packet

        packet: PacketType = [gen_damage]
        if isinstance(chosen, AVGECharacterCard) and chosen in bench_candidates and len(chosen.energy) > 0:
            def gen_discard_energy() -> PacketType:
                p: PacketType = []
                p.append(
                    AVGEEnergyTransfer(
                        chosen.energy[0],
                        chosen,
                        card.env,
                        ActionTypes.ATK_1,
                        card,
                        None,
                    )
                )
                return p
            packet.append(gen_discard_energy)

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, CathyRong)))
        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        def gen() -> PacketType:
            dmg = 50
            bench = [c for c in card.player.cardholders[Pile.BENCH] if isinstance(c, AVGECharacterCard) and c != card and c.card_type == CardType.PIANO]
            if len(bench) > 0:
                dmg = 80
            packet: PacketType = []
            packet.append(
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    dmg,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PIANO,
                    ActionTypes.ATK_2,
                    None,
                    card,
                )
            )
            return packet

        card.propose(
            AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_2, CathyRong))
        )

        return self.generic_response(card, ActionTypes.ATK_2)
