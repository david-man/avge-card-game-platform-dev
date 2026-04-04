from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *

class Bucket(AVGEToolCard):

    def __init__(self, unique_id):
        super().__init__(unique_id)
        self.original_type = None

    def deactivate_card(self):
        from card_game.internal_events import AVGECardAttributeChange

        super().deactivate_card()
        self.propose(
            AVGECardAttributeChange(
                self.card_attached,
                AVGECardAttribute.TYPE,
                self.original_type,
                AVGEAttributeModifier.SET_STATE,
                ActionTypes.ENV,
                self,
                None,
            )
        )

    def play_card(self, parent_event: AVGEEvent) -> Response:
        from card_game.avge_abstracts.AVGECardholder import AVGEToolCardholder
        from card_game.internal_events import AVGECardAttributeChange
        self.original_type = self.card_attached.attributes[AVGECardAttribute.TYPE]
        self.propose(
            AVGECardAttributeChange(
                self.card_attached,
                AVGECardAttribute.TYPE,
                CardType.PERCUSSION,
                AVGEAttributeModifier.SET_STATE,
                ActionTypes.PASSIVE,
                self,
                None,
            )
        )
        return self.generate_response()
