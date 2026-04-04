from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *


class BettySolomon(AVGECharacterCard):
    _ATK_1_KEY = "betty_deck_top"

    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.WOODWIND, 1, 1, 2)
        self.has_atk_1 = True
        self.atk_1_cost = 1
        self.has_atk_2 = True
        self.atk_2_cost = 2
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import InputEvent, TransferCard

        player = card.player
        deck = player.cardholders[Pile.DECK]
        character_cards = [candidate for candidate in deck.cards_by_id.values() if isinstance(candidate, AVGECharacterCard)]
        if len(character_cards) == 0:
            return card.generate_response()

        chosen_card = card.env.cache.get(card, BettySolomon._ATK_1_KEY, None, True)
        if chosen_card is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            player,
                            [BettySolomon._ATK_1_KEY],
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            {
                                "query_label": "betty_solomon_outreach",
                                "targets": character_cards,
                            },
                        )
                    ]
                },
            )

        card.propose(TransferCard(chosen_card, deck, deck, ActionTypes.ATK_1, card, 0))
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import AVGECardHPChange

        card.propose(
            [
                AVGECardHPChange(
                    lambda: card.player.opponent.get_active_card(),
                    50,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_2,
                    card,
                ),
                AVGECardHPChange(
                    card,
                    10,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_2,
                    card,
                ),
            ]
        )
        return card.generate_response()
