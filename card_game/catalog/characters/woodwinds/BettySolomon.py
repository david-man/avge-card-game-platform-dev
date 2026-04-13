from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class BettySolomon(AVGECharacterCard):
    _ATK_1_KEY = "betty_deck_top"

    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.WOODWIND, 1, 1, 2)
        self.has_atk_1 = True
        self.has_atk_2 = True
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, TransferCard, EmptyEvent

        player = card.player
        deck = player.cardholders[Pile.DECK]
        character_cards = [candidate for candidate in deck if isinstance(candidate, AVGECharacterCard)]
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
                                LABEL_FLAG: "betty_solomon_outreach",
                                TARGETS_FLAG: character_cards,
                                DISPLAY_FLAG:list(deck)
                            },
                        )
                    ]
                },
            )
        p : PacketType= [
                TransferCard(chosen_card, deck, deck, ActionTypes.ATK_1, card, 0)
            ]
        card.propose(AVGEPacket(p, AVGEEngineID(card, ActionTypes.ATK_1, BettySolomon))
        )
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange
        def gen() -> PacketType:
            return [
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
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
        card.propose(
            AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_2, BettySolomon))
        )
        return card.generate_response()
