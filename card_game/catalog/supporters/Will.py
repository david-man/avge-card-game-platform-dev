from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes


class Will(AVGESupporterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id)

    @staticmethod
    def play_card(card: AVGECard) -> Response:
        from card_game.internal_events import TransferCard
            
        def gen() -> PacketType:
            discard = card.player.cardholders[Pile.DISCARD]
            deck = card.player.cardholders[Pile.DECK]
            items_in_discard = [c for c in discard if isinstance(c, AVGEItemCard)]

            packet: PacketType = []
            for item_card in items_in_discard:
                packet.append(
                    TransferCard(
                        item_card,
                        discard,
                        deck,
                        ActionTypes.NONCHAR,
                        card,
                        random.randint(0, len(deck)),
                    )
                )
            return packet
            
        card.propose(AVGEPacket([gen], AVGEEngineID(card, ActionTypes.NONCHAR, Will)))

        return card.generate_response(ResponseType.CORE)
