from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class MikuOtomatoneEnergy(AVGEReactor):
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
		return "MikuOtomatone Effect"

	def react(self, args={}):
		from card_game.internal_events import AVGEEnergyTransfer, AtkPhase, EmptyEvent, TurnEnd

		event = self.attached_event
		boosted_character = self.owner_card.env.cache.get(self.owner_card, MikuOtomatone._BOOSTED_CHARACTER_KEY, None)
		if(isinstance(event, AtkPhase) and boosted_character is not None):
			if(len(self.owner_card.player.energy) >= 2):
				self.propose(
					[
						AVGEEnergyTransfer(
							self.owner_card.player.energy[0],
							self.owner_card.player,
							boosted_character,
							ActionTypes.NONCHAR,
							self.owner_card,
						),
						AVGEEnergyTransfer(
							self.owner_card.player.energy[1],
							self.owner_card.player,
							boosted_character,
							ActionTypes.NONCHAR,
							self.owner_card,
						),
					]
				)
				self.owner_card.env.cache.set(self.owner_card, MikuOtomatone._FIRST_TOKEN, self.owner_card.player.energy[0])
				self.owner_card.env.cache.set(self.owner_card, MikuOtomatone._SECOND_TOKEN, self.owner_card.player.energy[1])
			elif(len(self.owner_card.player.energy) == 1):
				self.propose(
					[
						AVGEEnergyTransfer(
							self.owner_card.player.energy[0],
							self.owner_card.player,
							boosted_character,
							ActionTypes.NONCHAR,
							self.owner_card,
						)
					]
				)
				self.owner_card.env.cache.set(self.owner_card, MikuOtomatone._FIRST_TOKEN, self.owner_card.player.energy[0])
		elif(isinstance(event, TurnEnd) and boosted_character is not None):
			self.owner_card.env.cache.delete(self.owner_card, MikuOtomatone._BOOSTED_CHARACTER_KEY)
			token_1 : EnergyToken = self.owner_card.env.cache.get(self.owner_card, MikuOtomatone._FIRST_TOKEN, None, True)
			token_2 : EnergyToken = self.owner_card.env.cache.get(self.owner_card, MikuOtomatone._SECOND_TOKEN, None, True)
			packet = []
			for token in [token_1, token_2]:
				if(token is not None and token.holder is not None):
					packet.append(
						AVGEEnergyTransfer(
							token,
							token.holder,
							self.owner_card.player,
							ActionTypes.PASSIVE,
							None
						)
					)
			if(len(packet) > 0):
				self.propose(packet)
			self.invalidate()
		else:
			self.propose([EmptyEvent("MikuOtomatone listener skipped unsupported event.", ActionTypes.PASSIVE, self.owner_card)])
			self.invalidate()
		return self.generate_response()


class MikuOtomatone(AVGEItemCard):
	_BOOSTED_CHARACTER_KEY = "miku_otomatone_boosted_character"
	_FIRST_TOKEN = "miku_otomatone_first_token"
	_SECOND_TOKEN = "miku_otomatone_second_token"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card_for: AVGECharacterCard, parent_event: AVGEEvent, args: Data = None) -> Response:
		from card_game.catalog.stadiums.AlumnaeHall import AlumnaeHall
		from card_game.catalog.stadiums.FriedmanHall import FriedmanHall
		from card_game.catalog.stadiums.RileyHall import RileyHall
		from card_game.catalog.stadiums.MainHall import MainHall
		env = card_for.env
		if(env.round_id == 0):
			return card_for.generate_response(ResponseType.SKIP, {"msg": "Cannot play MikuOtomatone on the first turn."})

		if(len(env.stadium_cardholder) == 0 or not isinstance(env.stadium_cardholder.peek(), (AlumnaeHall, FriedmanHall, RileyHall, MainHall))):
			return card_for.generate_response(ResponseType.SKIP, {"msg": "MikuOtomatone requires AlumnaeHall, FriedmanHall, RileyHall, or MainHall."})

		card_for.env.cache.set(card_for, MikuOtomatone._BOOSTED_CHARACTER_KEY, card_for.player.get_active_card())

		card_for.add_listener(MikuOtomatoneEnergy(card_for, card_for.env.round_id))
		return card_for.generate_response()
