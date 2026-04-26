from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import InputEvent, AVGEEnergyTransfer, AVGECardHPChange, TransferCard

class RyanLee(AVGECharacterCard):
    _ATK1_TARGET_KEY = "ryanlee_atk1_target"
    _ATK1_AMOUNT_KEY = "ryanlee_atk1_amount"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.PERCUSSION, 2, 1, 3)
        self.atk_1_name = 'Percussion Ensemble'
        self.atk_2_name = 'Four Mallets'

    def atk_1(self, card: AVGECharacterCard) -> Response:
        bench = card.player.cardholders[Pile.BENCH]
        candidates = [c for c in bench if isinstance(c, AVGECharacterCard) and c.card_type == CardType.PERCUSSION]
        max_attach = min(2, len(card.player.energy))
        if len(candidates) == 0 or max_attach == 0:
            return self.generic_response(card, ActionTypes.ATK_1)

        missing = object()
        chosen = card.env.cache.get(card, RyanLee._ATK1_TARGET_KEY, missing, True)
        if chosen is missing:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [RyanLee._ATK1_TARGET_KEY],
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            CardSelectionQuery(
                                'Percussion Ensemble: Choose a benched percussion character',
                                candidates,
                                list(bench),
                                False,
                                False,
                            )
                        )
                    ]),
            )

        if not isinstance(chosen, AVGECharacterCard) or chosen not in candidates:
            return self.generic_response(card, ActionTypes.ATK_1)

        energy_amt = card.env.cache.get(card, RyanLee._ATK1_AMOUNT_KEY, missing, True)
        if energy_amt is missing:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [RyanLee._ATK1_AMOUNT_KEY],
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            IntegerInputData('Choose energy to attach (up to 2)', 1, max_attach)
                        )
                    ]),
            )

        if not isinstance(energy_amt, int) or energy_amt <= 0:
            return self.generic_response(card, ActionTypes.ATK_1)

        transfer_count = min(energy_amt, max_attach)

        def generate_packet() -> PacketType:
            packet: PacketType = []
            for token in list(card.player.energy)[:transfer_count]:
                packet.append(AVGEEnergyTransfer(token, card.env, chosen, ActionTypes.ATK_1, card, None))
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, RyanLee)))
        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard) -> Response:
        packet: PacketType = []

        def make_hit():
            def hit() -> PacketType:
                p: PacketType = []
                p.append(AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    10,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PERCUSSION,
                    ActionTypes.ATK_2,
                    None,
                    card,
                ))
                return p
            return hit

        packet.extend([make_hit(), make_hit(), make_hit(), make_hit()])

        if len(card.player.cardholders[Pile.DECK]) > 0:
            def gen_draw() -> PacketType:
                p: PacketType = []
                p.append(
                    TransferCard(
                        card.player.cardholders[Pile.DECK].peek(),
                        card.player.cardholders[Pile.DECK],
                        card.player.cardholders[Pile.HAND],
                        ActionTypes.ATK_2,
                        card,
                        None,
                    )
                )
                return p
            packet.append(gen_draw)

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_2, RyanLee)))

        return self.generic_response(card, ActionTypes.ATK_2)
