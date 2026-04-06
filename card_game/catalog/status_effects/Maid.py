from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class MaidStatusDamageShieldModifier(AVGEModifier):
	def __init__(self):
		super().__init__(
			identifier=(None, ActionTypes.ENV),
			group=EngineGroup.INTERNAL_1,
			internal = True
		)

	def _has_maid(self, character: AVGECharacterCard | None) -> bool:
		if(not isinstance(character, AVGECharacterCard)):
			return False
		return len(character.statuses_attached.get(StatusEffect.MAID, [])) > 0

	def event_match(self, event):
		from card_game.internal_events import AVGECardHPChange

		if(not isinstance(event, AVGECardHPChange)):
			return False
		if(event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE):
			return False
		if(event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]):
			return False
		if(event.magnitude > 10):
			return False
		return self._has_maid(event.target_card)

	def event_effect(self) -> bool:
		return True

	def update_status(self):
		return

	def make_announcement(self) -> bool:
		return True

	def package(self):
		return "Maid Status Damage Shield"

	def modify(self, args={}):
		event = self.attached_event
		event.modify_magnitude(-10)
		return self.generate_response()
