from __future__ import annotations

from card_game.avge_abstracts import *

from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup

class GoonStatusTransferModifier(AVGEModifier):
	def __init__(self):
		super().__init__(
			identifier=AVGEEngineID(None, ActionTypes.ENV, None),
			group=EngineGroup.EXTERNAL_MODIFIERS_1,
		)
	def event_match(self, event):
		from card_game.internal_events import TransferCard

		return (
			isinstance(event, TransferCard)
			and isinstance(event.card, AVGECharacterCard)
			and len(event.card.statuses_attached.get(StatusEffect.GOON, [])) > 0
			and event.pile_from.pile_type == Pile.ACTIVE
			and event.pile_to.pile_type == Pile.BENCH
			and event.energy_requirement > 0
		)
	def event_effect(self) -> bool:
		return True

	def update_status(self):
		return

	def make_announcement(self) -> bool:
		return True

	def package(self):
		return "Goon Retreat Cost Modifier"
	
	def modify(self, args = {}) -> Response:
		from card_game.internal_events import TransferCard
		assert isinstance(self.attached_event, TransferCard)
		self.attached_event.energy_requirement += 1
		return self.generate_response()

class GoonStatusChangeReactor(AVGEReactor):
	def __init__(self):
		super().__init__(
			identifier=AVGEEngineID(None, ActionTypes.ENV, None),
			group=EngineGroup.EXTERNAL_REACTORS,
		)

	def event_match(self, event):
		from card_game.internal_events import AVGECardStatusChange

		return (
			isinstance(event, AVGECardStatusChange)
			and event.status_effect == StatusEffect.GOON
			and isinstance(event.target, AVGECharacterCard)
		)

	def event_effect(self) -> bool:
		return True

	def update_status(self):
		return

	def make_announcement(self) -> bool:
		return True

	def package(self):
		return "Goon On Status Change Reactor"

	def react(self, args={}):
		from card_game.internal_events import AVGECardHPChange, AVGECardMaxHPChange, AVGECardStatusChange
		assert isinstance(self.attached_event, AVGECardStatusChange)
		event: AVGECardStatusChange = self.attached_event
		target = event.target
		if(not isinstance(target, AVGECharacterCard)):
			return self.generate_response()

		packet : PacketType= []

		if(event.change_type == StatusChangeType.ADD and len(event.target.statuses_attached.get(StatusEffect.GOON, [])) == 1 and event.made_change):
			packet.extend([
				AVGECardMaxHPChange(target, 20, AVGEAttributeModifier.ADDITIVE, ActionTypes.ENV, None),
				AVGECardHPChange(target, 20, AVGEAttributeModifier.ADDITIVE, CardType.ALL, ActionTypes.ENV, None),
			])
		elif(event.change_type in [StatusChangeType.REMOVE, StatusChangeType.ERASE] and len(event.target.statuses_attached.get(StatusEffect.GOON, [])) == 0 and event.made_change):
			packet.extend([
				AVGECardMaxHPChange(target, 20, AVGEAttributeModifier.SUBSTRACTIVE, ActionTypes.ENV, None),
			])

		if(len(packet) > 0):
			self.extend_event(packet)
		return self.generate_response()
