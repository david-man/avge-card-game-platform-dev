from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class MaidOutfit(AVGEToolCard):

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def deactivate_card(self):
		from card_game.internal_events import AVGECardStatusChange

		
		assert self.card_attached is not None
		self.extend([
				AVGECardStatusChange(
				StatusEffect.MAID,
				StatusChangeType.ERASE,
				self.card_attached,
				ActionTypes.ENV,
				self,
				)
			]
		)
		super().deactivate_card()

	def play_card(self) -> Response:
		from card_game.internal_events import AVGECardStatusChange
		assert self.card_attached is not None
		self.propose(
			AVGEPacket([
				AVGECardStatusChange(
				StatusEffect.MAID,
				StatusChangeType.ADD,
				self.card_attached,
				ActionTypes.NONCHAR,
				self,
				)
			], AVGEEngineID(self, ActionTypes.NONCHAR, MaidOutfit))
		)

		return self.generate_response()
