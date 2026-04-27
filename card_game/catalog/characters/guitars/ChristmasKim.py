from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import ActionTypes, CardType, AVGEAttributeModifier, Response, ResponseType, Notify, RevealCards, all_players, default_timeout


class ChristmasKim(AVGECharacterCard):
    _ORDER_KEY = "christmaskim_order"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.GUITAR, 1, 1, 2)
        self.atk_1_name = 'Strum'
        self.atk_2_name = 'Surprise Delivery'

    def atk_1(self, card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        def gen() -> PacketType:
            return [
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    20,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.GUITAR,
                    ActionTypes.ATK_1,
                    None,
                    card,
                )
            ]
        card.propose(
            AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_1, ChristmasKim))
        )
        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, TransferCard, ReorderCardholder, AVGECardHPChange, EmptyEvent

        player = card.player
        deck = player.cardholders[Pile.DECK]
        hand = player.cardholders[Pile.HAND]

        n = min(5, len(deck))
        if n == 0:
            return Response(ResponseType.CORE, Notify(f"{str(card)} used Surprise Delivery, but there were no cards in deck.", all_players, default_timeout))
        top_cards = deck.peek_n(n)

        guitar_chars = [
            c for c in top_cards
            if isinstance(c, AVGECharacterCard) and c.card_type == CardType.GUITAR
        ]
        remaining_cards = [c for c in top_cards if c not in guitar_chars]

        packet: PacketType = []

        for c in guitar_chars:
            packet.append(
                TransferCard(c, deck, hand, ActionTypes.ATK_2, card, None)
            )
            packet.append(
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    20,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.GUITAR,
                    ActionTypes.ATK_2,
                    None,
                    card,
                )
            )

        if len(guitar_chars) > 0:
            packet.append(
                EmptyEvent(
                    ActionTypes.ATK_2,
                    card,
                    ResponseType.CORE,
                    RevealCards("Surprise Delivery: Revealed guitar characters", all_players, default_timeout, list(guitar_chars)),
                )
            )

        if len(remaining_cards) > 1:
            keys = [ChristmasKim._ORDER_KEY + str(i) for i in range(len(remaining_cards))]
            order_choice = [card.env.cache.get(card, key, None, True) for key in keys]
            if order_choice[0] is None:
                return Response(
                    ResponseType.INTERRUPT,
                    Interrupt[AVGEEvent]([
                            InputEvent(
                                player,
                                keys,
                                lambda r: True,
                                ActionTypes.ATK_2,
                                card,
                                CardSelectionQuery(
                                    "Surprise Delivery: Reorder remaining cards",
                                    remaining_cards,
                                    remaining_cards,
                                    False,
                                    False,
                                )
                            )
                        ]),
                )

            new_order = list(deck.get_order())
            for c in top_cards:
                cid = c.unique_id
                if cid in new_order:
                    new_order.remove(cid)
            chosen_order = [choice for choice in order_choice if isinstance(choice, AVGECard) and choice in remaining_cards]
            chosen_ids = [choice.unique_id for choice in chosen_order]
            remaining_ids = [c.unique_id for c in remaining_cards if c.unique_id not in chosen_ids]
            new_order = chosen_ids + remaining_ids + new_order
            packet.append(ReorderCardholder(deck, new_order, ActionTypes.ATK_2, card, None))

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_2, ChristmasKim)))
        return self.generic_response(card, ActionTypes.ATK_2)
