from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class KikisHeadband(AVGEToolCard):

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def deactivate_card(self):
		from card_game.internal_events import AVGECardAttributeChange

		super().deactivate_card()

		self.propose(
			AVGECardAttributeChange(
				self.card_attached,
				AVGECardAttribute.SWITCH_COST,
				1,
				AVGEAttributeModifier.ADDITIVE,
				ActionTypes.NONCHAR,
				self,
				None,
			)
		)

	def play_card(self, parent_event: AVGEEvent) -> Response:
		from card_game.avge_abstracts.AVGECardholder import AVGEToolCardholder
		from card_game.internal_events import AVGECardAttributeChange

		self.propose(
			AVGECardAttributeChange(
				self.card_attached,
				AVGECardAttribute.SWITCH_COST,
				1,
				AVGEAttributeModifier.SUBSTRACTIVE,
				ActionTypes.NONCHAR,
				self,
				None,
			)
		)

		return self.generate_response()
