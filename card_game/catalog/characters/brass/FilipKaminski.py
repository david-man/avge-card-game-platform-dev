from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from typing import cast
from card_game.internal_events import InputEvent, TransferCard, AVGECardHPChange

class FilipKaminski(AVGECharacterCard):
    _TYPE_CHOICE_KEY = "filip_type_choice"
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.BRASS, 2, 1, 3)
        self.atk_1_name = 'Heart of the Cards'
        self.atk_2_name = 'Intense Echo'

    def atk_1(self, card: AVGECharacterCard) -> Response:
        deck = card.player.cardholders[Pile.DECK]
        hand = card.player.cardholders[Pile.HAND]
        if len(deck) == 0:
            return Response(ResponseType.CORE, Notify(f"{str(card)} used Heart of the Cards, but it did nothing...", all_players, default_timeout))

        possible_names = sorted({
            type(c).__name__
            for zone in (
                card.player.cardholders[Pile.DECK],
                card.player.cardholders[Pile.BENCH],
                card.player.cardholders[Pile.HAND],
                card.player.cardholders[Pile.ACTIVE],
                card.player.cardholders[Pile.DISCARD],
            )
            for c in zone
        })

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
                                "Heart of the Cards: Name a card.",
                                possible_names,
                                possible_names,
                                False,
                                False
                            )
                        )
                    ]
                )
            )

        chosen_name = chosen_val if isinstance(chosen_val, str) else str(chosen_val)

        top = deck.peek()
        card.propose(AVGEPacket([TransferCard(top, deck, hand, ActionTypes.ATK_1, card, None)], 
                                AVGEEngineID(card, ActionTypes.ATK_1, FilipKaminski)))
        if type(top).__name__ == chosen_name:
            def atk() -> PacketType:
                active = card.player.opponent.get_active_card()
                packet: PacketType = []
                if isinstance(active, AVGECharacterCard):
                    packet.append(
                        AVGECardHPChange(
                            active,
                            50,
                            AVGEAttributeModifier.SUBSTRACTIVE,
                            CardType.BRASS,
                            ActionTypes.ATK_1,
                            None,
                            card,
                        )
                    )
                return packet
            card.propose(AVGEPacket([atk], AVGEEngineID(card, ActionTypes.ATK_1, FilipKaminski)))

            return Response(ResponseType.CORE, Notify(f"{str(card)} used Heart of the Cards and it HIT!", all_players, default_timeout))
        return Response(ResponseType.CORE, Notify(f"{str(card)} used Heart of the Cards, but it didn't hit...", all_players, default_timeout))

    def atk_2(self, card: AVGECharacterCard) -> Response:
        opponent = card.player.opponent
        opponent_bench : AVGECardholder = opponent.cardholders[Pile.BENCH]
        stadium_bonus = (
            len(card.env.stadium_cardholder) > 0
            and isinstance(card.env.stadium_cardholder.peek(), AVGEStadiumCard)
            and card.env.stadium_cardholder.peek().player == card.player
        )

        def generate_packet() -> PacketType:
            p: PacketType = []
            active = opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                p.append(
                    AVGECardHPChange(
                        active,
                        50,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.BRASS,
                        ActionTypes.ATK_2,
                        None,
                        card,
                    )
                )

            if stadium_bonus:
                p += [AVGECardHPChange(
                    cast(AVGECharacterCard, target),
                    20,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.BRASS,
                    ActionTypes.ATK_2,
                    None,
                    card,
                ) for target in opponent_bench] 
            return p

        card.propose(
            AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_2, FilipKaminski))
        )
        return self.generic_response(card, ActionTypes.ATK_2)
