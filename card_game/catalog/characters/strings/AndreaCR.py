from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import InputEvent, ReorderCardholder, EmptyEvent, AVGECardHPChange, AVGEEnergyTransfer

class AndreaCR(AVGECharacterCard):
    _REORDER_BASE_KEY = "andreacr_reorder_top"
    _ENERGY_REMOVAL_KEY = "andreacr_energy_removal_target"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 1, 1, 3)
        self.atk_1_name = 'Foresight'
        self.atk_2_name = 'Snap Pizz'

    def atk_1(self, card: AVGECharacterCard) -> Response:
        opponent_deck = card.player.opponent.cardholders[Pile.DECK]
        consider_count = min(3, len(opponent_deck))
        if consider_count == 0:
            return self.generic_response(card, ActionTypes.ATK_1)

        top_cards = list(opponent_deck.peek_n(consider_count))
        keys = [AndreaCR._REORDER_BASE_KEY + str(i) for i in range(consider_count)]
        chosen_order = [card.env.cache.get(card, key, None, True) for key in keys]
        if len(chosen_order) == 0 or chosen_order[0] is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            keys,
                            lambda res : True,
                            ActionTypes.ATK_1,
                            card,
                            CardSelectionQuery(
                                'Foresight: Reorder the top cards of your opponent deck',
                                top_cards,
                                top_cards,
                                False,
                                False,
                            )
                        )
                    ]),
            )

        chosen_cards = [c for c in chosen_order if isinstance(c, AVGECard)]

        original_order = list(opponent_deck.get_order())
        top_ids = [c.unique_id for c in top_cards]
        chosen_ids = [c.unique_id for c in chosen_cards]
        remaining_ids = [cid for cid in original_order if cid not in top_ids]
        new_order = chosen_ids + remaining_ids

        card.propose(
            AVGEPacket(
                [
                    ReorderCardholder(
                        opponent_deck,
                        new_order,
                        ActionTypes.ATK_1,
                        card,
                        None,
                    )
                ],
                AVGEEngineID(card, ActionTypes.ATK_1, AndreaCR),
            )
        )
        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard) -> Response:
        opponent = card.player.opponent
        chosen_target = card.env.cache.get(card, AndreaCR._ENERGY_REMOVAL_KEY, None, True)
        targets = [c for c in opponent.get_cards_in_play() if isinstance(c, AVGECharacterCard)]

        if chosen_target is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [AndreaCR._ENERGY_REMOVAL_KEY],
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            CardSelectionQuery(
                                'Snap Pizz: Choose one opposing character to remove up to 2 energy from',
                                targets,
                                targets,
                                False,
                                False,
                            )
                        )
                    ]),
            )

        def gen() -> PacketType:
            packet: PacketType = []
            active = opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        20,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.STRING,
                        ActionTypes.ATK_2,
                        None,
                        card,
                    )
                )
            return packet

        assert isinstance(chosen_target, AVGECharacterCard)

        def gen1() -> PacketType:
            k: PacketType = []
            for token in list(chosen_target.energy)[:min(2, len(chosen_target.energy))]:
                k.append(
                    AVGEEnergyTransfer(
                        token,
                        chosen_target,
                        chosen_target.env,
                        ActionTypes.ATK_2,
                        card,
                        None,
                    )
                )
            return k

        packet: PacketType = [gen, gen1]
        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_2, AndreaCR)))
        return self.generic_response(card, ActionTypes.ATK_2)
