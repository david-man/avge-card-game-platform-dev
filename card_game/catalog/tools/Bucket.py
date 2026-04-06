from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *

class Bucket(AVGEToolCard):

    def __init__(self, unique_id):
        super().__init__(unique_id)
        self.original_type : CardType | None = None

    def deactivate_card(self):
        from card_game.internal_events import AVGECardTypeChange
        assert self.card_attached is not None
        assert self.original_type is not None
        super().deactivate_card()
        self.propose(
            AVGEPacket([
                AVGECardTypeChange(
                    self.card_attached,
                    self.original_type,
                    ActionTypes.ENV,
                    None,
                )
            ], AVGEEngineID(None, ActionTypes.ENV, None))
        )

    def play_card(self) -> Response:
        from card_game.avge_abstracts.AVGECardholder import AVGEToolCardholder
        from card_game.internal_events import AVGECardTypeChange
        assert self.card_attached is not None
        self.original_type = self.card_attached.card_type
        self.propose(
            AVGEPacket([
                AVGECardTypeChange(
                    self.card_attached,
                    CardType.PERCUSSION,
                    ActionTypes.ENV,
                    None,
                )
            ], AVGEEngineID(self, ActionTypes.PASSIVE, Bucket))
        )
        return self.generate_response()
