from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *
from typing import Type
from card_game.internal_events import InputEvent, TransferCard, AVGECardHPChange

class FilipKaminski(AVGECharacterCard):
    _TYPE_CHOICE_KEY = "filip_type_choice"
    def __init__(self, unique_id):
        super().__init__(unique_id, 120, CardType.BRASS, 2)
        self.has_atk_1 = True
        self.atk_1_cost = 1
        self.has_atk_2 = True
        self.atk_2_cost = 2
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        possible_types = set([type(c) for c in 
                              card.player.cardholders[Pile.DECK]] + 
                              [type(c) for c in 
                              card.player.cardholders[Pile.BENCH]] + 
                              [type(c) for c in 
                              card.player.cardholders[Pile.HAND]] + 
                              [type(c) for c in 
                              card.player.cardholders[Pile.ACTIVE]] + 
                              [type(c) for c in 
                              card.player.cardholders[Pile.DISCARD]])
        deck = card.player.cardholders[Pile.DECK]
        hand = card.player.cardholders[Pile.HAND]
        if len(deck) == 0:
            return card.generate_response()
        top = deck.peek()
        card.propose([TransferCard(top, deck, hand, ActionTypes.ATK_1, card)])
        chosen_val = card.env.cache.get(card, FilipKaminski._TYPE_CHOICE_KEY, None, one_look=True)
        if chosen_val is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [FilipKaminski._TYPE_CHOICE_KEY],
                            InputType.SELECTION,
                            lambda r : True,
                            ActionTypes.ATK_1,
                            card,
                            {"query_label": "filip-type-guess",
                             "targets": list(possible_types)},
                        )
                    ]
                },
            )


        top_type = type(top)
        if top_type == chosen_val:
            card.propose(AVGECardHPChange(
                lambda : card.player.opponent.get_active_card(),
                60,
                AVGEAttributeModifier.SUBSTRACTIVE,
                ActionTypes.ATK_1,
                CardType.BRASS,
                card,
            ))

        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        opponent = card.player.opponent
        opponent_bench : AVGECardholder = opponent.cardholders[Pile.BENCH]
        card.propose(
            lambda : [
                AVGECardHPChange(
                    target,
                    10,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    ActionTypes.ATK_2,
                    CardType.BRASS,
                    card,
                ) for target in opponent_bench] + 
                [AVGECardHPChange(
                    opponent.get_active_card(),
                    50,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    ActionTypes.ATK_2,
                    CardType.BRASS,
                    card
                )]
        )

        return card.generate_response()
