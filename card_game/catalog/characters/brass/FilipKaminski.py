from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from typing import cast
from card_game.internal_events import InputEvent, TransferCard, AVGECardHPChange

class FilipKaminski(AVGECharacterCard):
    _TYPE_CHOICE_KEY = "filip_type_choice"
    def __init__(self, unique_id):
        super().__init__(unique_id, 120, CardType.BRASS, 2, 1, 2)
        self.atk_1_name = 'Heart of the Cards'
        self.atk_1_name = 'Intense Echo'

    def atk_1(self, card: AVGECharacterCard) -> Response:
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
            return Response(ResponseType.CORE, Notify(f"{str(card)} used Heart of the Cards, but it did nothing...", all_players, default_timeout))
        chosen_val = card.env.cache.get(card, FilipKaminski._TYPE_CHOICE_KEY, None, one_look=True)
        if chosen_val is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[InputEvent](
                    [
                        InputEvent(
                            card.player,
                            [FilipKaminski._TYPE_CHOICE_KEY],
                            lambda r : True,
                            ActionTypes.ATK_1,
                            card,
                            StrSelectionQuery(
                                "Heart of the Cards: Guess the card on the top of your deck",
                                list(str(possible_types)),
                                list(str(possible_types)),
                                False,
                                False
                            )
                        )
                    ]
                )
            )

        top = deck.peek()
        card.propose(AVGEPacket([TransferCard(top, deck, hand, ActionTypes.ATK_1, card, None)], 
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
                    None,
                    card,
                )]
            card.propose(AVGEPacket([atk], AVGEEngineID(card, ActionTypes.ATK_1, FilipKaminski)))

            return Response(ResponseType.CORE, Notify(f"{str(card)} used Heart of the Cards and it HIT!", all_players, default_timeout))
        return Response(ResponseType.CORE, Notify(f"{str(card)} used Heart of the Cards, but it didn't hit...", all_players, default_timeout))
    def atk_2(self, card: AVGECharacterCard) -> Response:
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
                    None,
                    card,
                ) for target in opponent_bench] 
            p += [AVGECardHPChange(
                    opponent.get_active_card(),
                    50,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.BRASS,
                    ActionTypes.ATK_2,
                    None,
                    card
                )]
            return p
        card.propose(
            AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_2, FilipKaminski))
        )
        return self.generic_response(card, ActionTypes.ATK_2)
