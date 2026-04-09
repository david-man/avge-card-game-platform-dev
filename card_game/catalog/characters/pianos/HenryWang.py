from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class HenryWang(AVGECharacterCard):
    _LAST_ATK1_ROUND_KEY = "henry_atk1_last_round"

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.PIANO, 1, 1, 3)
        self.has_atk_1 = True
        self.has_atk_2 = True
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        last_round = card.env.cache.get(card, HenryWang._LAST_ATK1_ROUND_KEY, None)
        if last_round is not None and card.env.round_id - last_round <= 2:
            return card.generate_response(data={MESSAGE_KEY: "You cannot use this attack this turn!"})
        def gen() -> PacketType:
            return [
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    30,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PIANO,
                    ActionTypes.ATK_1,
                    card,
                )
            ]
        card.propose(
            AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_1, HenryWang))
        )

        card.env.cache.set(card, HenryWang._LAST_ATK1_ROUND_KEY, card.env.round_id)
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange, TransferCard

        opponent = card.player.opponent

        def generate_packet():
            deck = opponent.cardholders[Pile.DECK]
            discard = opponent.cardholders[Pile.DISCARD]

            damage = 20
            packet : PacketType = []
            if len(deck) > 0:
                top = deck.peek()
                packet.append(TransferCard(top, deck, discard, ActionTypes.ATK_2, card))
                if isinstance(top, AVGEItemCard):
                    damage = 100

            packet.insert(
                0,
                AVGECardHPChange(
                    opponent.get_active_card(),
                    damage,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PIANO,
                    ActionTypes.ATK_2,
                    card,
                ),
            )
            return packet
        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_2, HenryWang)))
        return card.generate_response()
