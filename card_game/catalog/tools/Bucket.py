from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes


class Bucket(AVGEToolCard):

    def __init__(self, unique_id):
        super().__init__(unique_id)
        self.original_type : CardType | None = None

    def deactivate_card(self):
        from card_game.internal_events import AVGECardTypeChange

        assert self.card_attached is not None
        assert self.original_type is not None
        
        packet : PacketType = []
        packet.extend([
                AVGECardTypeChange(
                    self.card_attached,
                    self.original_type,
                    ActionTypes.ENV,
                    self,
                    None,
                )
            ])
        super().deactivate_card()
        return packet

    def play_card(self) -> Response:
        from card_game.internal_events import AVGECardTypeChange

        assert self.card_attached is not None
        self.original_type = self.card_attached.card_type
        self.propose(
            AVGEPacket([
                AVGECardTypeChange(
                    self.card_attached,
                    CardType.PERCUSSION,
                    ActionTypes.NONCHAR,
                    self,
                    None,
                )
            ], AVGEEngineID(self, ActionTypes.PASSIVE, Bucket))
        )

        return Response(ResponseType.CORE, Data())
