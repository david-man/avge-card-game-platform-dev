from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *
from card_game.internal_events import InputEvent, TransferCard


class BenCherekIII(AVGECharacterCard):
    _YES_NO_KEY = "bencherek_yn_key"

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.GUITAR, 2, 2)
        self.has_atk_1 = True
        self.atk_1_cost = 2
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        yn = card.env.cache.get(card, BenCherekIII._YES_NO_KEY, None, True)
        if yn is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [BenCherekIII._YES_NO_KEY],
                            InputType.BINARY,
                            lambda r: True,
                            ActionTypes.PASSIVE,
                            card,
                            {"query_label": "ben_cherek_yn_key"},
                        )
                    ]
                },
            )

        if yn:
            card.propose([
                TransferCard(
                    lambda: card.player.get_active_card(),
                    card.player.cardholders[Pile.ACTIVE],
                    card.player.cardholders[Pile.BENCH],
                    ActionTypes.PASSIVE,
                    card,
                ),
                TransferCard(
                    card,
                    card.cardholder,
                    card.player.cardholders[Pile.ACTIVE],
                    ActionTypes.PASSIVE,
                    card,
                ),
            ])
        return card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import AVGECardHPChange

        packet = [
            AVGECardHPChange(
                lambda: card.player.opponent.get_active_card(),
                50,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.GUITAR,
                ActionTypes.ATK_1,
                card,
            )
        ]

        for c in card.player.cardholders[Pile.BENCH]:
            if c.card_type == CardType.GUITAR:
                packet.append(
                    AVGECardHPChange(
                        c,
                        10,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.GUITAR,
                        ActionTypes.ATK_1,
                        card,
                    )
                )

        card.propose(packet)
        return card.generate_response()
