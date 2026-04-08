from __future__ import annotations

from card_game.avge_abstracts import *

from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.constants import ActionTypes

class MikuOtomatoneEnergy(AVGEReactor):
	def __init__(self, owner_card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard, round_played):
		super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.NONCHAR, MikuOtomatone), group=EngineGroup.EXTERNAL_REACTORS)
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

	def react(self, args=None):
		from card_game.internal_events import AVGEEnergyTransfer, AtkPhase, TurnEnd

		event = self.attached_event
		assert isinstance(event, AtkPhase | TurnEnd)
		boosted_character = self.owner_card.env.cache.get(self.owner_card, MikuOtomatone._BOOSTED_CHARACTER_KEY, None)
		if(isinstance(event, AtkPhase) and boosted_character is None):
			self.owner_card.env.cache.set(self.owner_card, MikuOtomatone._BOOSTED_CHARACTER_KEY, self.owner_card.player.get_active_card())
			if(len(self.owner_card.player.energy) >= 2):
				packet : PacketType = [
						AVGEEnergyTransfer(
							self.owner_card.player.energy[0],
							self.owner_card.player,
							self.owner_card.player.get_active_card(),
							ActionTypes.NONCHAR,
							self.owner_card,
						),
						AVGEEnergyTransfer(
							self.owner_card.player.energy[1],
							self.owner_card.player,
							self.owner_card.player.get_active_card(),
							ActionTypes.NONCHAR,
							self.owner_card,
						),
					]
				self.propose(
					AVGEPacket(packet, AVGEEngineID(self.owner_card, ActionTypes.NONCHAR, MikuOtomatone))
				)
				self.owner_card.env.cache.set(self.owner_card, MikuOtomatone._FIRST_TOKEN, self.owner_card.player.energy[0])
				self.owner_card.env.cache.set(self.owner_card, MikuOtomatone._SECOND_TOKEN, self.owner_card.player.energy[1])
			elif(len(self.owner_card.player.energy) == 1):
				packet : PacketType = [
						AVGEEnergyTransfer(
							self.owner_card.player.energy[0],
							self.owner_card.player,
							self.owner_card.player.get_active_card(),
							ActionTypes.NONCHAR,
							self.owner_card,
						)
					]
				self.propose(
					AVGEPacket(packet, AVGEEngineID(self.owner_card, ActionTypes.NONCHAR, MikuOtomatone))
				)
				self.owner_card.env.cache.set(self.owner_card, MikuOtomatone._FIRST_TOKEN, self.owner_card.player.energy[0])
		elif(isinstance(event, TurnEnd) and boosted_character is not None):
			self.owner_card.env.cache.delete(self.owner_card, MikuOtomatone._BOOSTED_CHARACTER_KEY)
			token_1 = self.owner_card.env.cache.get(self.owner_card, MikuOtomatone._FIRST_TOKEN, None, True)
			token_2  = self.owner_card.env.cache.get(self.owner_card, MikuOtomatone._SECOND_TOKEN, None, True)
			
			packet = []
			for token in [token_1, token_2]:
				if(token is not None and isinstance(token ,EnergyToken) and token.holder is not None):
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
				self.propose(AVGEPacket(packet, AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, MikuOtomatone)))
			self.invalidate()
		return self.generate_response()


class MikuOtomatone(AVGEItemCard):
	_BOOSTED_CHARACTER_KEY = "miku_otomatone_boosted_character"
	_FIRST_TOKEN = "miku_otomatone_first_token"
	_SECOND_TOKEN = "miku_otomatone_second_token"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card) -> Response:
		from card_game.catalog.stadiums.AlumnaeHall import AlumnaeHall
		from card_game.catalog.stadiums.FriedmanHall import FriedmanHall
		from card_game.catalog.stadiums.RileyHall import RileyHall
		from card_game.catalog.stadiums.MainHall import MainHall
		env = card.env
		if(env.round_id == 0):
			return card.generate_response(ResponseType.SKIP, {MESSAGE_KEY: "Cannot play MikuOtomatone on the first turn."})

		if(len(env.stadium_cardholder) == 0 or not isinstance(env.stadium_cardholder.peek(), (AlumnaeHall, FriedmanHall, RileyHall, MainHall))):
			return card.generate_response(ResponseType.SKIP, {MESSAGE_KEY: "MikuOtomatone requires AlumnaeHall, FriedmanHall, RileyHall, or MainHall."})

		card.add_listener(MikuOtomatoneEnergy(card, card.env.round_id))
		return card.generate_response()
