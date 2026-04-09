from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from typing import cast
from card_game.internal_events import InputEvent, TransferCard, AVGECardHPChange

class FilipKaminski(AVGECharacterCard):
    _TYPE_CHOICE_KEY = "filip_type_choice"
    def __init__(self, unique_id):
        super().__init__(unique_id, 120, CardType.BRASS, 2, 1, 2)
        self.has_atk_1 = True
        self.has_atk_2 = True
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
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
            return card.generate_response(data={MESSAGE_KEY: "no cards in deck!"})
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
                            {"query_label": "filip_type_guess",
                             "targets": list(possible_types),
                             "display": list(possible_types)},
                        )
                    ]
                },
            )

        top = deck.peek()
        card.propose(AVGEPacket([TransferCard(top, deck, hand, ActionTypes.ATK_1, card)], 
                                AVGEEngineID(card, ActionTypes.ATK_1, FilipKaminski)))
        top_type = type(top)
        if top_type == chosen_val:
            def atk() -> PacketType:
                return [AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    60,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.BRASS,
                    ActionTypes.ATK_1,
                    card,
                )]
            card.propose(AVGEPacket([atk], AVGEEngineID(card, ActionTypes.ATK_1, FilipKaminski)))

        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        opponent = card.player.opponent
        opponent_bench : AVGECardholder = opponent.cardholders[Pile.BENCH]
        def generate_packet() -> PacketType:
            p : PacketType = [
                AVGECardHPChange(
                    cast(AVGECharacterCard, target),
                    10,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.BRASS,
                    ActionTypes.ATK_2,
                    card,
                ) for target in opponent_bench] 
            p += [AVGECardHPChange(
                    opponent.get_active_card(),
                    50,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.BRASS,
                    ActionTypes.ATK_2,
                    card
                )]
            return p
        card.propose(
            AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_2, FilipKaminski))
        )

        return card.generate_response()
