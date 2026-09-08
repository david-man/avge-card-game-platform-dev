from __future__ import annotations

from card_game.avge_abstracts import *

from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class MaidStatusDamageShieldModifier(AVGEModifier):
	def __init__(self, env : AVGEEnvironment):
		self.env = env
		super().__init__(
			identifier=AVGEEngineID(env, ActionTypes.ENV, None),
			group=EngineGroup.INTERNAL_1
		)

	def _has_maid(self, character: AVGECharacterCard | None) -> bool:
		if(not isinstance(character, AVGECharacterCard)):
			return False
		return len(character.statuses_attached.get(StatusEffect.MAID, [])) > 0

	def _eligible_damage_event(self, event):
		from card_game.internal_events import AVGECardHPChange

		if(not isinstance(event, AVGECardHPChange)):
			return None
		if(event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE):
			return None
		if(event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]):
			return None
		if(event.magnitude > 10):
			return None
		if(event.change_type == CardType.ALL):
			return None
		if(not self._has_maid(event.target_card)):
			return None
		return event

	def event_match(self, event):
		return self._eligible_damage_event(event) is not None

	def event_effect(self) -> bool:
		return self._eligible_damage_event(self.attached_event) is not None

	def update_status(self):
		return

	def make_announcement(self) -> bool:
		return True

	def __str__(self):
		return "Maid Status Damage Shield"

	def modify(self, args={}):
		event = self._eligible_damage_event(self.attached_event)
		if(event is None):
			return Response(ResponseType.ACCEPT, Data())
		return Response(ResponseType.FAST_FORWARD, Notify("Maid: This character is immune to all damage <= 10", all_players, default_timeout))
