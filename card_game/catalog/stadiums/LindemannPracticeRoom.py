from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEConstrainer import *
from card_game.constants import *


class LindemannReducedAttackCostConstraint(AVGEConstraint):
	def __init__(self, owner_card: AVGEStadiumCard):
		super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, LindemannPracticeRoom))
		self.owner_card = owner_card

	def _bench_shares_active_type(self, player: AVGEPlayer) -> bool:
		active_card = player.get_active_card()
		assert isinstance(active_card, AVGECharacterCard)
		active_type = active_card.card_type
		for benched_card in player.cardholders[Pile.BENCH]:
			if(not isinstance(benched_card, AVGECharacterCard)):
				return False
			if(benched_card.card_type != active_type):
				return False
		return True

	def match(self, obj):
		from card_game.internal_events import PlayCharacterCard
		from card_game.internal_listeners import AVGEPlayCharacterCardValidityCheck

		if(not self.owner_card._is_active_stadium()):
			return False
		if(not isinstance(obj, AVGEPlayCharacterCardValidityCheck)):
			return False

		event = obj.attached_event
		if(not isinstance(event, PlayCharacterCard)):
			return False
		if(event.catalyst_action != ActionTypes.PLAYER_CHOICE):
			return False
		if(event.card_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]):
			return False
		if(not isinstance(event.caller_card, AVGECharacterCard)):
			return False

		if(not self._bench_shares_active_type(event.caller_card.env.player_turn)):
			return False

		if(not isinstance(obj, (AVGEAbstractEventListener, AVGEConstraint))):
			return False
		energy_attached = len(event.card.energy)
		required_energy = int(event.card.atk_1_cost if event.card_action == ActionTypes.ATK_1 else event.card.atk_2_cost)
		reduced_requirement = max(0, required_energy - 1)
		return energy_attached >= reduced_requirement

	def update_status(self):
		if(not self.owner_card._is_active_stadium()):
			self.invalidate()

	def make_announcement(self) -> bool:
		return True

	def package(self):
		return "LindemannPracticeRoom Constraint"


class LindemannPracticeRoom(AVGEStadiumCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self) -> Response:
		owner_card = self

		if(owner_card.original_owner is None):
			owner_card.original_owner = owner_card.player

		owner_card.add_constrainer(LindemannReducedAttackCostConstraint(owner_card))
		return owner_card.generate_response()
