from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from typing import cast

class AndreaCR(AVGECharacterCard):
    _REORDER_BASE_KEY = "andreacr_reorder_top"
    _ENERGY_REMOVAL_KEY = "andreacr_energy_removal_target"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 1, 1, 3)
        self.has_atk_1 = True
        self.atk_1_cost = 1
        self.has_atk_2 = True
        self.atk_2_cost = 3
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, ReorderCardholder, EmptyEvent

        opponent_deck = card.player.opponent.cardholders[Pile.DECK]
        if len(opponent_deck) == 0:
            return card.generate_response(data={MESSAGE_KEY: "Opponent deck has nothing in it!"})

        consider_count = min(3, len(opponent_deck))
        top_cards = list(opponent_deck.peek_n(consider_count))
        keys = [AndreaCR._REORDER_BASE_KEY + str(i) for i in range(consider_count)]
        chosen_order = [card.env.cache.get(card, key, None, True) for key in keys]
        if chosen_order[0] is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            keys,
                            InputType.SELECTION,
                            lambda res : True,
                            ActionTypes.ATK_1,
                            card,
                            {
                                "query_label": "andrea_c_r_atk1_reorder",
                                "target": top_cards,
                                "display": top_cards
                            },
                        )
                    ]
                },
            )
        chosen_ids = [cast(AVGECharacterCard, c).unique_id for c in chosen_order]
        original_order = list(opponent_deck.get_order())
        new_order = chosen_ids + [k for k in original_order if k not in chosen_ids]
        card.propose(
            AVGEPacket([
                ReorderCardholder(opponent_deck, new_order, ActionTypes.ATK_1, card)
            ], AVGEEngineID(card, ActionTypes.ATK_1, AndreaCR))
        )
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, AVGECardHPChange, AVGEEnergyTransfer

        opponent = card.player.opponent
        chosen_target = card.env.cache.get(card, AndreaCR._ENERGY_REMOVAL_KEY, None, True)
        if chosen_target is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [AndreaCR._ENERGY_REMOVAL_KEY],
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            {
                                "query_label": "andrea_c_r_snap_pizz",
                                "targets": opponent.get_cards_in_play(),
                                "display": opponent.get_cards_in_play()
                            },
                        )
                    ]
                },
            )
        def gen() -> PacketType:
            return [
                AVGECardHPChange(
                    opponent.get_active_card(),
                    20,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.STRING,
                    ActionTypes.ATK_2,
                    card,
                )
            ]
        assert isinstance(chosen_target, AVGECharacterCard) 
        def gen_2() -> PacketType:
            return [AVGEEnergyTransfer(token, chosen_target, chosen_target.player, ActionTypes.ATK_2, card) for token in list(chosen_target.energy)[:min(2, len(chosen_target.energy))]]
        packet : PacketType = [gen, gen_2]
        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_2, AndreaCR)))
        return card.generate_response()
