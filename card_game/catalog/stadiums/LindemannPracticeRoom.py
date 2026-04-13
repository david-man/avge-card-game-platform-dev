from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.avge_abstracts.AVGECards import AVGEStadiumCard
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class LindemannReducedAttackCostModifier(AVGEModifier):
	def __init__(self, owner_card: AVGEStadiumCard):
		super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, LindemannPracticeRoom), group=EngineGroup.EXTERNAL_MODIFIERS_1)
		self.owner_card = owner_card

	def _bench_shares_active_type(self, player: AVGEPlayer) -> bool:
		active_card = player.get_active_card()
		if(not isinstance(active_card, AVGECharacterCard)):
			return False
		active_type = active_card.card_type
		for benched_card in player.cardholders[Pile.BENCH]:
			if(not isinstance(benched_card, AVGECharacterCard)):
				return False
			if(benched_card.card_type != active_type):
				return False
		return True

	def event_match(self, event):
		from card_game.internal_events import PlayCharacterCard

		if(not self.owner_card._is_active_stadium()):
			return False
		if(not isinstance(event, PlayCharacterCard)):
			return False
		if(event.catalyst_action != ActionTypes.PLAYER_CHOICE):
			return False
		if(event.card_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]):
			return False
		if(not isinstance(event.card, AVGECharacterCard)):
			return False
		if(not event.energy_requirement > 0):
			return False
		if(not self._bench_shares_active_type(event.card.player)):
			return False
		return True

	def event_effect(self) -> bool:
		return True

	def update_status(self):
		if(not self.owner_card._is_active_stadium()):
			self.invalidate()

	def make_announcement(self) -> bool:
		return True

	def package(self):
		return "LindemannPracticeRoom Reduced Attack Cost"

	def modify(self, args=None):
		from card_game.internal_events import PlayCharacterCard

		event = self.attached_event
		assert isinstance(event, PlayCharacterCard)
		event.energy_requirement = max(0, event.energy_requirement - 1)
		return self.generate_response()


class LindemannPracticeRoom(AVGEStadiumCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self) -> Response:
		owner_card = self

		owner_card.add_listener(LindemannReducedAttackCostModifier(owner_card))
		return owner_card.generate_response()
