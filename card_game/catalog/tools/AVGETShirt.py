from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class AVGETShirt(AVGEToolCard):

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def deactivate_card(self):
		from card_game.internal_events import AVGECardStatusChange
		assert self.card_attached is not None
		
		self.extend_event([
				AVGECardStatusChange(
				StatusEffect.GOON,
				StatusChangeType.ERASE,
				self.card_attached,
				ActionTypes.ENV,
				self,
				None,
				)
			]
		)
		super().deactivate_card()
	
	def play_card(self) -> Response:
		assert self.card_attached is not None
		from card_game.internal_events import AVGECardStatusChange
		self.propose(
			AVGEPacket([
				AVGECardStatusChange(
				StatusEffect.GOON,
				StatusChangeType.ADD,
				self.card_attached,
				ActionTypes.NONCHAR,
				self,
				None,
				)
			], AVGEEngineID(self, ActionTypes.NONCHAR, AVGETShirt))
		)

		return Response(ResponseType.CORE, Data())
