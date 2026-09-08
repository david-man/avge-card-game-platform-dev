from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import AVGECardHPChange, InputEvent


class RedRoomAmpDiff(AVGEModifier):
	def __init__(self, owner_card: AVGEStadiumCard):
		super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, RedRoom), group=EngineGroup.EXTERNAL_MODIFIERS_2)
		self.owner_card = owner_card

	def _is_supported_attack_event(self, event) -> bool:
		if(not self.owner_card._is_active_stadium()):
			return False
		if(not isinstance(event, AVGECardHPChange)):
			return False
		if(event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE):
			return False
		if(event.change_type == CardType.ALL):
			return False
		if(event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]):
			return False
		if(not isinstance(event.caller, AVGECharacterCard)):
			return False
		caller_type = event.caller.card_type
		return caller_type in [CardType.GUITAR, CardType.PIANO, CardType.CHOIR, CardType.PERCUSSION, CardType.WOODWIND, CardType.BRASS]

	def event_match(self, event):
		return self._is_supported_attack_event(event)

	def update_status(self):
		if(not self.owner_card._is_active_stadium()):
			self.invalidate()

	def modify(self, args=None):
		event = self.attached_event
		assert isinstance(event, AVGECardHPChange)
		assert isinstance(event.caller, AVGECharacterCard)

		if(event.caller.card_type in [CardType.WOODWIND, CardType.BRASS]):
			event.modify_magnitude(-10)
		else:
			event.modify_magnitude(10)
		return Response(ResponseType.ACCEPT, Notify("Red Room: Amp Diff", all_players, default_timeout))
	
	def __str__(self):
		return "Red Room: Amp Diff"


class RedRoom(AVGEStadiumCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	def __str__(self):
		return "Red Room"

	def play_card(self) -> Response:
		self.add_listener(RedRoomAmpDiff(self))
		return Response(ResponseType.CORE, Data())
