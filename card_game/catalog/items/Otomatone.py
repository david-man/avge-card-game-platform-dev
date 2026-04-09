from __future__ import annotations

from card_game.avge_abstracts import *

from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class OtomatoneEnergy(AVGEModifier):
	def __init__(self, owner_card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard, round_played):
		super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.NONCHAR, Otomatone), group=EngineGroup.EXTERNAL_MODIFIERS_1)
		self.owner_card = owner_card
		self.round_played = round_played

	def event_match(self, event):
		from card_game.internal_events import PlayCharacterCard

		if(not isinstance(event, PlayCharacterCard)):
			return False
		if(event.catalyst_action != ActionTypes.PLAYER_CHOICE):
			return False
		if(event.card_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]):
			return False
		if(event.card.player != self.owner_card.player):
			return False
		if(event.card != self.owner_card.player.get_active_card()):
			return False
		if(event.energy_requirement <= 0):
			return False
		return True

	def event_effect(self) -> bool:
		return True

	def update_status(self):
		if(self.owner_card.env.round_id > self.round_played):
			self.invalidate()

	def make_announcement(self) -> bool:
		return True

	def package(self):
		return "Otomatone Effect"

	def modify(self, args=None):
		from card_game.internal_events import PlayCharacterCard

		assert isinstance(self.attached_event, PlayCharacterCard)
		event : PlayCharacterCard = self.attached_event
		event.energy_requirement = max(0, event.energy_requirement - 1)
		return self.generate_response()


class Otomatone(AVGEItemCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)


	@staticmethod
	def play_card(card) -> Response:

		if(card.env.round_id == 0):
			return card.generate_response(ResponseType.SKIP, {MESSAGE_KEY: "Cannot play Otomatone on the first turn of round one."})

		card.add_listener(OtomatoneEnergy(card, card.env.round_id))
		return card.generate_response()
