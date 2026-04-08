from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.catalog.items.ConcertProgram import ConcertProgram
from card_game.catalog.items.ConcertTicket import ConcertTicket


class SarahChen(AVGECharacterCard):
    _DISCARD_SELECTION_KEY = "sarah_discard_selection"
    _TARGET_SELECTION_KEY = "sarah_target_selection"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.WOODWIND, 1, 1, 3)
        self.has_atk_1 = True
        self.atk_1_cost = 1
        self.has_atk_2 = True
        self.atk_2_cost = 3
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange
        def gen() -> PacketType:
            return [
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    10,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_1,
                    card,
                )
            ]
        card.propose(
            AVGEPacket([gen for _ in range(2)], AVGEEngineID(card, ActionTypes.ATK_1, SarahChen))
        )
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange, InputEvent, TransferCard

        player = card.player
        hand = player.cardholders[Pile.HAND]
        discard = player.cardholders[Pile.DISCARD]
        opponent = card.player.opponent

        eligible_cards = [
            hand_card
            for hand_card in hand
            if isinstance(hand_card, (ConcertProgram, ConcertTicket))
        ]
        if len(eligible_cards) == 0:
            return card.generate_response(data={MESSAGE_KEY: "No concert programs or tickets in hand!"})

        discard_selection = card.env.cache.get(card, SarahChen._DISCARD_SELECTION_KEY, None)
        if discard_selection is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            player,
                            [SarahChen._DISCARD_SELECTION_KEY],
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            {
                                "query_label": "sarah_chen_atk_2_discard",
                                "targets": eligible_cards,
                                "display": list(hand)
                            },
                        )
                    ]
                },
            )
        target_selection = card.env.cache.get(card, SarahChen._TARGET_SELECTION_KEY, None, True)
        if target_selection is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            player,
                            [SarahChen._TARGET_SELECTION_KEY],
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            {
                                "query_label": "sarah_chen_atk_2_target",
                                "targets": opponent.get_cards_in_play(),
                                "display": opponent.get_cards_in_play()
                            },
                        )
                    ]
                },
            )
        assert isinstance(target_selection, AVGECharacterCard)
        card.propose(
            AVGEPacket([
                TransferCard(
                    discard_selection,
                    hand,
                    discard,
                    ActionTypes.ATK_2,
                    card,
                ),
                AVGECardHPChange(
                    target_selection,
                    40,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_2,
                    card,
                ),
            ], AVGEEngineID(card, ActionTypes.ATK_2, SarahChen))
        )
        card.env.cache.delete(card, SarahChen._DISCARD_SELECTION_KEY)
        return card.generate_response()
