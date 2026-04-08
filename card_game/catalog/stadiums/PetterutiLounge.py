from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.avge_abstracts.AVGECards import AVGEStadiumCard
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.catalog.items.MatchaLatte import MatchaLatte
from card_game.catalog.items.StrawberryMatchaLatte import StrawberryMatchaLatte

from card_game.internal_events import AVGECardHPChange, TransferCard


class PetterutiMaidDamageModifier(AVGEModifier):
	def __init__(self, owner_card: AVGEStadiumCard):
		super().__init__(
			identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, PetterutiLounge),
			group=EngineGroup.EXTERNAL_MODIFIERS_2,
		)
		self.owner_card = owner_card

	def event_match(self, event):
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
		return len(event.caller_card.statuses_attached.get(StatusEffect.MAID, [])) > 0

	def event_effect(self) -> bool:
		return True

	def update_status(self):
		if(not self.owner_card._is_active_stadium()):
			self.invalidate()

	def modify(self, args=None):
		event = self.attached_event
		assert isinstance(event, AVGECardHPChange)
		event.modify_magnitude(10)
		return self.generate_response()


class PetterutiMaidTransfer(AVGEModifier):
	def __init__(self, owner_card: AVGEStadiumCard):
		super().__init__(
			identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, PetterutiLounge),
			group=EngineGroup.EXTERNAL_MODIFIERS_2,
		)
		self.owner_card = owner_card

	def event_match(self, event):
		if(not self.owner_card._is_active_stadium()):
			return False
		if(not isinstance(event, TransferCard)):
			return False
		if(not isinstance(event.caller_card, AVGECharacterCard)):
			return False
		if(not (event.pile_to.pile_type == Pile.ACTIVE and event.pile_from.pile_type == Pile.BENCH)):
			return False
		return len(event.caller_card.statuses_attached.get(StatusEffect.MAID, [])) > 0

	def event_effect(self) -> bool:
		return True

	def update_status(self):
		if(not self.owner_card._is_active_stadium()):
			self.invalidate()

	def modify(self, args=None):
		event = self.attached_event
		assert isinstance(event, TransferCard)
		event.energy_requirement = 0
		return self.generate_response()


class PetterutiLounge(AVGEStadiumCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self) -> Response:
		self.add_listener(PetterutiMaidDamageModifier(self))
		self.add_listener(PetterutiMaidTransfer(self))

		return self.generate_response()
