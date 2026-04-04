from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class MusescoreSubscription(AVGEToolCard):

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def deactivate_card(self):
		from card_game.internal_events import AVGEStatusChange

		super().deactivate_card()

		self.propose(
			AVGEStatusChange(
				self.card_attached,
				StatusEffect.ARRANGER,
				StatusChangeType.REMOVE,
				ActionTypes.ENV,
				self,
			)
		)

	def play_card(self, parent_event: AVGEEvent) -> Response:
		from card_game.internal_events import AVGEStatusChange

		self.propose(
			AVGEStatusChange(
				self.card_attached,
				StatusEffect.ARRANGER,
				StatusChangeType.ADD,
				ActionTypes.ENV,
				self,
			)
		)

		return self.generate_response()
