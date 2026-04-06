from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class MusescoreSubscription(AVGEToolCard):

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def deactivate_card(self):
		from card_game.internal_events import AVGECardStatusChange

		super().deactivate_card()

		assert self.card_attached is not None
		self.propose(
			AVGEPacket([
				AVGECardStatusChange(
				StatusEffect.ARRANGER,
				StatusChangeType.REMOVE,
				self.card_attached,
				ActionTypes.NONCHAR,
				self,
				)
			], AVGEEngineID(None, ActionTypes.ENV, None))
		)

	def play_card(self) -> Response:
		from card_game.internal_events import AVGECardStatusChange
		assert self.card_attached is not None
		self.propose(
			AVGEPacket([
				AVGECardStatusChange(
				StatusEffect.ARRANGER,
				StatusChangeType.ADD,
				self.card_attached,
				ActionTypes.NONCHAR,
				self,
				)
			], AVGEEngineID(self, ActionTypes.NONCHAR, MusescoreSubscription))
		)

		return self.generate_response()
