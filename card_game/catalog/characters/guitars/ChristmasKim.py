from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import ActionTypes, CardType, AVGEAttributeModifier, Response, ResponseType, Notify, RevealCards, all_players, default_timeout


class ChristmasKim(AVGECharacterCard):
    _ORDER_KEY = "christmaskim_order"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.GUITAR, 2, 1, 2)
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

        n = min(3, len(deck))
        if n == 0:
            return Response(ResponseType.CORE, Notify(f"{str(card)} used Surprise Delivery, but there were no cards in deck.", all_players, default_timeout))
        top_cards = deck.peek_n(n)

        char_cards = [c for c in top_cards if isinstance(c, AVGECharacterCard)]
        nonchars = [c for c in top_cards if not isinstance(c, AVGECharacterCard)]

        packet: PacketType = []

        for c in char_cards:
            packet.append(
                TransferCard(c, deck, hand, ActionTypes.ATK_2, card, None)
            )
            packet.append(
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    10,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.GUITAR,
                    ActionTypes.ATK_2,
                    None,
                    card,
                )
            )

        if len(nonchars) > 0:
            keys = [ChristmasKim._ORDER_KEY + str(i) for i in range(len(nonchars))]
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
                                CardSelectionQuery("Surprise Delivery: Reorder remaining cards", nonchars, char_cards + nonchars, False, False)
                            )
                        ]),
                )

            new_order = list(deck.get_order())
            for c in top_cards:
                cid = c.unique_id
                if cid in new_order:
                    new_order.remove(cid)
            chosen_order = [choice for choice in order_choice if choice is not None]
            new_order = [choice.unique_id for choice in chosen_order] + new_order
            if len(char_cards) > 0:
                revealed_cards: list[AVGECard] = [c for c in char_cards]
                packet.append(
                    EmptyEvent(
                        ActionTypes.ATK_2,
                        card,
                        ResponseType.CORE,
                        RevealCards("Surprise Delivery: Revealed characters", all_players, default_timeout, revealed_cards),
                    )
                )
            packet.append(ReorderCardholder(deck, new_order, ActionTypes.ATK_2, card, None))

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_2, ChristmasKim)))
        return self.generic_response(card, ActionTypes.ATK_2)
