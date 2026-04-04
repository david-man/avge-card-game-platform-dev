from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *


class ChristmasKim(AVGECharacterCard):
    _ORDER_KEY = "christmaskim_order"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.GUITAR, 2, 1, 2)
        self.has_atk_1 = True
        self.atk_1_cost = 1
        self.has_atk_2 = True
        self.atk_2_cost = 2
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import AVGECardHPChange

        card.propose(
            AVGECardHPChange(
                lambda: card.player.opponent.get_active_card(),
                20,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.GUITAR,
                ActionTypes.ATK_1,
                card,
            )
        )
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import InputEvent, TransferCard, ReorderCardholder, AVGECardHPChange

        player = card.player
        deck = player.cardholders[Pile.DECK]
        hand = player.cardholders[Pile.HAND]

        n = min(3, len(deck))
        if n == 0:
            return card.generate_response()
        top_cards = deck.peek_n(n)

        char_cards = [c for c in top_cards if isinstance(c, AVGECharacterCard)]
        nonchars = [c for c in top_cards if not isinstance(c, AVGECharacterCard)]

        packet = []

        for c in char_cards:
            packet.append(TransferCard(c, deck, hand, ActionTypes.ATK_2, card))
            packet.append(
                AVGECardHPChange(
                    lambda: card.player.opponent.get_active_card(),
                    10,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.GUITAR,
                    ActionTypes.ATK_2,
                    card,
                )
            )

        if len(nonchars) == 1:
            packet.append(TransferCard(nonchars[0], deck, deck, ActionTypes.ATK_2, card, 0))
        elif len(nonchars) > 1:
            keys = [ChristmasKim._ORDER_KEY + str(i) for i in range(len(nonchars))]
            order_choice = [card.env.cache.get(card, key, None, True) for key in keys]
            if order_choice[0] is None:
                return card.generate_response(
                    ResponseType.INTERRUPT,
                    {
                        INTERRUPT_KEY: [
                            InputEvent(
                                player,
                                keys,
                                InputType.SELECTION,
                                lambda r: True,
                                ActionTypes.ATK_2,
                                card,
                                {
                                    "query_label": "christmas-reorder-top",
                                    "targets": nonchars,
                                },
                            )
                        ]
                    },
                )

            new_order = list(deck.get_order())
            for c in top_cards:
                cid = c.unique_id
                if cid in new_order:
                    new_order.remove(cid)
            new_order = [choice.unique_id for choice in order_choice] + new_order
            packet.append(ReorderCardholder(deck, new_order, ActionTypes.ATK_2, card))

        card.propose(packet)
        return card.generate_response()
