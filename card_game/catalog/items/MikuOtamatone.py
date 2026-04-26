from __future__ import annotations

from card_game.avge_abstracts import *

from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import PlayCharacterCard
from card_game.catalog.stadiums.AlumnaeHall import AlumnaeHall
from card_game.catalog.stadiums.FriedmanHall import FriedmanHall
from card_game.catalog.stadiums.RileyHall import RileyHall
from card_game.catalog.stadiums.MainHall import MainHall

class MikuOtamatoneEnergy(AVGEModifier):
	def __init__(self, owner_card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard, round_played):
		super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.NONCHAR, MikuOtamatone), group=EngineGroup.EXTERNAL_MODIFIERS_1)
		self.owner_card = owner_card
		self.round_played = round_played

	def event_match(self, event):
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

	def modify(self, args=None):
		assert isinstance(self.attached_event, PlayCharacterCard)
		event : PlayCharacterCard = self.attached_event
		event.energy_requirement = max(0, event.energy_requirement - 2)
		return Response(ResponseType.ACCEPT, Notify('Miku Otamatone: Active has +2 effective energy this turn.', all_players, default_timeout))


class MikuOtamatone(AVGEItemCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self, card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:
		env = card.env
		if(env.round_id == 0):
			return Response(ResponseType.SKIP, Notify('Cannot play Miku Otamatone on the first turn.', [card.player.unique_id], default_timeout))

		if(len(env.stadium_cardholder) == 0 or not isinstance(env.stadium_cardholder.peek(), (AlumnaeHall, FriedmanHall, RileyHall, MainHall))):
			return Response(ResponseType.SKIP, Notify('Miku Otamatone can only be played in concert halls.', [card.player.unique_id], default_timeout))

		card.add_listener(MikuOtamatoneEnergy(card, card.env.round_id))
		return self.generic_response(card)
