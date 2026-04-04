from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import PlayNonCharacterCard

class MainHallPlayLimitAssessor(AVGEAssessor):
	def __init__(self, owner_card: AVGEStadiumCard, round : int):
		super().__init__(identifier=(owner_card, AVGEEventListenerType.PASSIVE), group=EngineGroup.EXTERNAL_PRECHECK_1)
		self.owner_card = owner_card
		self.round_active = round

	def event_match(self, event):

		if(not self.owner_card._is_active_stadium()):
			return False
		if(not isinstance(event, PlayNonCharacterCard)):
			return False
		if(not self.owner_card.env.round_id >= self.round_active):
			return False
		if(not event.catalyst_action == ActionTypes.PLAYER_CHOICE):
			return False
		player_id = event.card.player.unique_id
		if(player_id == str(PlayerID.P1)):
			count = int(self.owner_card.env.cache.get(self.owner_card, MainHall._P1_COUNT_KEY, 0))
		else:
			count = int(self.owner_card.env.cache.get(self.owner_card, MainHall._P2_COUNT_KEY, 0))
		return count >= 3

	def update_status(self):
		if(not self.owner_card._is_active_stadium()):
			self.invalidate()

	def make_announcement(self) -> bool:
		return True

	def package(self):
		return "MainHall Assessor"

	def assess(self, args={}):
		return self.generate_response(ResponseType.SKIP, {"msg": "MainHall: player already played 3 non-character cards this turn."})


class MainHallCountPlayReactor(AVGEReactor):
	def __init__(self, owner_card: AVGEStadiumCard, round : int):
		super().__init__(identifier=(owner_card, AVGEEventListenerType.PASSIVE), group=EngineGroup.EXTERNAL_REACTORS)
		self.owner_card = owner_card
		self.round_active = round

	def event_match(self, event):
		

		if(not self.owner_card._is_active_stadium()):
			return False
		if(not isinstance(event, PlayNonCharacterCard)):
			return False
		if(not self.owner_card.env.round_id >= self.round_active):
			return False
		if(not event.catalyst_action == ActionTypes.PLAYER_CHOICE):
			return False
		return True

	def update_status(self):
		if(not self.owner_card._is_active_stadium()):
			self.invalidate()

	def make_announcement(self) -> bool:
		return True

	def package(self):
		return "MainHall Reactor"

	def react(self, args={}):
		event : PlayNonCharacterCard= self.attached_event
		player_id = event.card.player.unique_id
		if(player_id == str(PlayerID.P1)):
			count = int(self.owner_card.env.cache.get(self.owner_card, MainHall._P1_COUNT_KEY, 0))
			self.owner_card.env.cache.set(self.owner_card, MainHall._P1_COUNT_KEY, count + 1)
		else:
			count = int(self.owner_card.env.cache.get(self.owner_card, MainHall._P2_COUNT_KEY, 0))
			self.owner_card.env.cache.set(self.owner_card, MainHall._P2_COUNT_KEY, count + 1)
		return self.generate_response()


class MainHallTurnStartResetReactor(AVGEReactor):
	def __init__(self, owner_card: AVGEStadiumCard):
		super().__init__(identifier=(owner_card, AVGEEventListenerType.PASSIVE), group=EngineGroup.EXTERNAL_REACTORS)
		self.owner_card = owner_card

	def event_match(self, event):
		from card_game.internal_events import PhasePickCard
		return self.owner_card._is_active_stadium() and isinstance(event, PhasePickCard)

	def update_status(self):
		if(not self.owner_card._is_active_stadium()):
			self.invalidate()

	def make_announcement(self) -> bool:
		return True

	def package(self):
		return "MainHall Reactor"

	def react(self, args={}):
		event = self.attached_event
		player_id = event.player.unique_id
		if(player_id == str(PlayerID.P1)):
			self.owner_card.env.cache.set(self.owner_card, MainHall._P1_COUNT_KEY, 0)
		else:
			self.owner_card.env.cache.set(self.owner_card, MainHall._P2_COUNT_KEY, 0)
		return self.generate_response()

class MainHall(AVGEStadiumCard):
	_ENABLED_KEY = "mainhall_enabled"
	_PENDING_ENABLE_KEY = "mainhall_pending_enable"
	_P1_COUNT_KEY = "mainhall_p1_noncharacter_count"
	_P2_COUNT_KEY = "mainhall_p2_noncharacter_count"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self, parent_event: AVGEEvent) -> Response:
		owner_card = self

		if(owner_card.original_owner is None):
			owner_card.original_owner = owner_card.player

		if(owner_card.env.round_id == 0):
			return owner_card.generate_response(ResponseType.SKIP, {"msg": "MainHall cannot be played on the first turn."})
		owner_card.env.cache.set(owner_card, MainHall._P1_COUNT_KEY, 0)
		owner_card.env.cache.set(owner_card, MainHall._P2_COUNT_KEY, 0)

		owner_card.add_listener(MainHallPlayLimitAssessor(owner_card, owner_card.env.round_id + 1))
		owner_card.add_listener(MainHallCountPlayReactor(owner_card, owner_card.env.round_id + 1))
		owner_card.add_listener(MainHallTurnStartResetReactor(owner_card, owner_card.env.round_id + 1))
		return owner_card.generate_response()
