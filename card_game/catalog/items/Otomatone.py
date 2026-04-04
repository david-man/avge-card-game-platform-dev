from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class OtomatoneEnergy(AVGEReactor):
	def __init__(self, owner_card: AVGEItemCard, round_played):
		super().__init__(identifier=(owner_card, AVGEEventListenerType.NONCHAR), group=EngineGroup.EXTERNAL_REACTORS)
		self.owner_card = owner_card
		self.round_played = round_played

	def event_match(self, event):
		from card_game.internal_events import AtkPhase, TurnEnd
		return isinstance(event, AtkPhase) or isinstance(event, TurnEnd)

	def event_effect(self) -> bool:
		return True

	def update_status(self):
		if(self.owner_card.env.round_id > self.round_played):
			self.invalidate()

	def make_announcement(self) -> bool:
		return True

	def package(self):
		return "Otomatone Effect"

	def react(self, args={}):
		from card_game.internal_events import AVGEEnergyTransfer, AtkPhase, TurnEnd

		event = self.attached_event
		boosted_character = self.owner_card.env.cache.get(self.owner_card, Otomatone._BOOSTED_CHARACTER_KEY, self.owner_card.player.get_active_card())

		if(isinstance(event, AtkPhase) and boosted_character is not None and len(self.owner_card.player.energy) > 0):
			self.owner_card.env.cache.set(self.owner_card, Otomatone._BOOSTED_CHARACTER_KEY, boosted_character)
			self.owner_card.env.cache.set(self.owner_card, Otomatone._TOKEN_KEY, self.owner_card.player.energy[0])
			self.propose(AVGEEnergyTransfer(self.owner_card.player.energy[0], self.owner_card.player, boosted_character, ActionTypes.NONCHAR, self.owner_card))
		elif(isinstance(event, TurnEnd) and boosted_character is not None):
			token : EnergyToken = self.owner_card.env.cache.get(self.owner_card, Otomatone._TOKEN_KEY, None, True)
			if(token is not None):
				self.propose(AVGEEnergyTransfer(token, boosted_character, self.owner_card.player, ActionTypes.NONCHAR, self.owner_card))
			self.invalidate()
		else:
			raise Exception("Something went very badly.")
		return self.generate_response()


class Otomatone(AVGEItemCard):
	_BOOSTED_CHARACTER_KEY = "otomatone_boosted_character"
	_TOKEN_KEY = "otomatone_token_key"
	def __init__(self, unique_id):
		super().__init__(unique_id)


	@staticmethod
	def play_card(card_for: AVGECharacterCard, parent_event: AVGEEvent, args: Data = None) -> Response:

		if(card_for.env.round_id == 0):
			return card_for.generate_response(ResponseType.SKIP, {"msg": "Cannot play Otomatone on the first turn of round one."})

		card_for.env.cache.set(card_for, Otomatone._BOOSTED_CHARACTER_KEY, card_for.player.get_active_card())

		card_for.add_listener(OtomatoneEnergy(card_for, card_for.env.round_id))
		return card_for.generate_response()
