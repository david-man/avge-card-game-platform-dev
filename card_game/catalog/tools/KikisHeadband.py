from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import AVGEModifier
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class KikisHeadbandTransferModifier(AVGEModifier):
	def __init__(self, owner_card: AVGEToolCard):
		super().__init__(
			identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, KikisHeadband),
			group=EngineGroup.EXTERNAL_MODIFIERS_1,
		)
		self.owner_card = owner_card

	def event_match(self, event):
		from card_game.internal_events import TransferCard

		if(not isinstance(event, TransferCard)):
			return False
		if(self.owner_card.card_attached is None):
			return False
		if(event.card != self.owner_card.card_attached):
			return False
		if(event.pile_from.pile_type != Pile.ACTIVE):
			return False
		if(event.pile_to.pile_type != Pile.BENCH):
			return False
		if(event.energy_requirement <= 0):
			return False
		return True

	def event_effect(self) -> bool:
		return True

	def update_status(self):
		if(self.owner_card.cardholder is None or self.owner_card.cardholder.pile_type == Pile.DISCARD):
			self.invalidate()

	def make_announcement(self) -> bool:
		return True

	def package(self):
		return "KikisHeadband Switch Cost Modifier"

	def modify(self, args=None):
		from card_game.internal_events import TransferCard

		assert isinstance(self.attached_event, TransferCard)
		event: TransferCard = self.attached_event
		event.energy_requirement = max(0, event.energy_requirement - 1)
		return self.generate_response()


class KikisHeadband(AVGEToolCard):

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self) -> Response:
		self.add_listener(KikisHeadbandTransferModifier(self))
		return self.generate_response()
