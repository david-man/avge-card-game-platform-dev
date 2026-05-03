from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import PlayNonCharacterCard, TransferCard


class MainHallPlayLimitAssessor(AVGEAssessor):
	def __init__(self, owner_card: AVGEStadiumCard, round : int):
		super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, MainHall), group=EngineGroup.EXTERNAL_PRECHECK_1)
		self.owner_card = owner_card
		self.round_active = round

	def _is_counted_transfer(self, event: TransferCard, player: AVGEPlayer) -> bool:
		return (
			event.card.player == player
			and event.catalyst_action == ActionTypes.PLAYER_CHOICE
			and event.pile_from.pile_type == Pile.HAND
			and event.pile_to.pile_type == Pile.BENCH
		)

	def _count_player_plays_this_round(self, player: AVGEPlayer) -> int:
		env = self.owner_card.env
		round_id = env.round_id
		count = 0

		nonchar_idx = 0
		while True:
			event, found_idx = env.check_history(round_id, PlayNonCharacterCard, {}, nonchar_idx)
			if event is None:
				break
			assert isinstance(event, PlayNonCharacterCard)
			if event.card.player == player and event.catalyst_action == ActionTypes.PLAYER_CHOICE:
				count += 1
			nonchar_idx = found_idx + 1

		transfer_idx = 0
		while True:
			event, found_idx = env.check_history(round_id, TransferCard, {}, transfer_idx)
			if event is None:
				break
			assert isinstance(event, TransferCard)
			if self._is_counted_transfer(event, player):
				count += 1
			transfer_idx = found_idx + 1

		return count

	def event_match(self, event):
		if(not self.owner_card._is_active_stadium()):
			return False
		if(not self.owner_card.env.round_id >= self.round_active):
			return False
		if(not event.catalyst_action == ActionTypes.PLAYER_CHOICE):
			return False
		if(not isinstance(event, (PlayNonCharacterCard, TransferCard))):
			return False
		if(isinstance(event, TransferCard)
		   and (event.pile_from.pile_type != Pile.HAND or event.pile_to.pile_type != Pile.BENCH)):
			return False
		player = event.card.player
		count = self._count_player_plays_this_round(player)
		return count >= 3

	def update_status(self):
		if(not self.owner_card._is_active_stadium()):
			self.invalidate()

	def assess(self, args=None):
		return Response(ResponseType.SKIP, Notify('Main Hall: Small Ensemble Limit prevented this action!', all_players, default_timeout))


class MainHall(AVGEStadiumCard):
	_ENABLED_KEY = "mainhall_enabled"
	_PENDING_ENABLE_KEY = "mainhall_pending_enable"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self) -> Response:
		owner_card = self
		if(owner_card.env.round_id == 0):
			return Response(ResponseType.SKIP, Notify('MainHall cannot be played on the first turn.', [owner_card.player.unique_id], default_timeout))
		owner_card.add_listener(MainHallPlayLimitAssessor(owner_card, owner_card.env.round_id + 1))
		return Response(ResponseType.CORE, Data())
