from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class SalomonDECIAttackBoostModifier(AVGEModifier):
	def __init__(self, owner_card: AVGEStadiumCard):
		super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, SalomonDECI), group=EngineGroup.EXTERNAL_MODIFIERS_2)
		self.owner_card = owner_card

	def _is_supported_attack_event(self, event) -> bool:
		from card_game.internal_events import AVGECardHPChange

		if(not self.owner_card._is_active_stadium()):
			return False
		if(not isinstance(event, AVGECardHPChange)):
			return False
		if(event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE):
			return False
		if(event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]):
			return False
		if(not isinstance(event.caller_card, AVGECharacterCard)):
			return False
		caller_type = event.caller_card.card_type
		return caller_type in [CardType.GUITAR, CardType.PIANO, CardType.CHOIR, CardType.PERCUSSION]

	def event_match(self, event):
		return self._is_supported_attack_event(event)

	def update_status(self):
		if(not self.owner_card._is_active_stadium()):
			self.invalidate()

	def modify(self, args=None):
		from card_game.internal_events import InputEvent, AVGECardHPChange

		event = self.attached_event
		assert isinstance(event, AVGECardHPChange)
		roll = self.owner_card.env.cache.get(self.owner_card, SalomonDECI._D6_ROLL_KEY, None, one_look=True)
		if(roll is None):
			assert event.caller_card is not None
			return self.generate_response(
				ResponseType.INTERRUPT,
				{INTERRUPT_KEY: 
	 					[InputEvent(
							 event.caller_card.player, 
							 [SalomonDECI._D6_ROLL_KEY], 
							 InputType.D6, 
							 lambda r: True, 
							 ActionTypes.PASSIVE, 
							 self.owner_card, 
							 {LABEL_FLAG: "DECI_D6"})]},
			)

		if(int(roll) >= 3):
			event.modify_magnitude(30)
		return self.generate_response()


class SalomonDECI(AVGEStadiumCard):
	_D6_ROLL_KEY = "salomondeci_runtime_d6_roll"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self) -> Response:
		self.add_listener(SalomonDECIAttackBoostModifier(self))
		return self.generate_response()
