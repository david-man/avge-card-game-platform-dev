from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import AVGEModifier
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup

from card_game.internal_events import AVGECardHPChange


class BUOStandNextAttackModifier(AVGEModifier):
	def __init__(self, owner_card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard, round_played):
		super().__init__(
			identifier=AVGEEngineID(owner_card, ActionTypes.NONCHAR, BUOStand),
			group=EngineGroup.EXTERNAL_MODIFIERS_2,
		)
		self.owner_card = owner_card
		self.round_played = round_played

	def event_match(self, event):
		if(not isinstance(event, AVGECardHPChange)):
			return False
		if(event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE):
			return False
		if(event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]):
			return False
		return True
	def event_effect(self) -> bool:
		return True
	
	def update_status(self):
		if(self.owner_card.env.round_id != self.round_played):
			self.invalidate()

	def make_announcement(self) -> bool:
		return True

	def package(self):
		return "BUOStand Modifier"
	
	def on_packet_completion(self):
		self.invalidate()
		return super().on_packet_completion()

	def modify(self, args=None):
		event = self.attached_event
		assert isinstance(event, AVGECardHPChange)
		event.modify_magnitude(20)
		return self.generate_response()

class BUOStand(AVGEItemCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card) -> Response:
		from card_game.internal_events import AVGEEnergyTransfer

		active = card.player.get_active_card()
		if(len(active.energy) == 0):
			return card.generate_response(ResponseType.SKIP, {"msg": "no energy on active character -- cannot play BUOStand"})
		card.add_listener(BUOStandNextAttackModifier(card, card.env.round_id))
		card.propose(
			AVGEPacket([
				AVGEEnergyTransfer(active.energy[0], active, active.player, ActionTypes.NONCHAR, card)
			], AVGEEngineID(card, ActionTypes.NONCHAR, BUOStand))
		)
		return card.generate_response()
