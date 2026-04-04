from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class EmmaNextTurnSwapLockAssessor(AVGEAssessor):
	def __init__(self, owner_card: AVGESupporterCard, locked_character: AVGECharacterCard, opponent: AVGEPlayer, round_active : int):
		super().__init__(
			identifier=(owner_card, AVGEEventListenerType.NONCHAR),
			group=EngineGroup.EXTERNAL_PRECHECK_1,
		)
		self.owner_card = owner_card
		self.locked_character = locked_character
		self.opponent = opponent
		self.round_active = round_active

	def event_match(self, event):
		from card_game.internal_events import TransferCard

		if(not isinstance(event, TransferCard)):
			return False
		if(event.catalyst_action != ActionTypes.PLAYER_CHOICE):
			return False
		if(event.pile_from.pile_type != Pile.ACTIVE):
			return False
		if(event.pile_to.pile_type != Pile.BENCH):
			return False
		if(event.card != self.locked_character):
			return False
		if(event.card.player != self.opponent):
			return False
		if(self.env.round_id != self.round_active):
			return False
		return True

	def event_effect(self) -> bool:
		return True

	def update_status(self):
		if(self.env.round_id > self.round_active):
			self.invalidate()

	def make_announcement(self) -> bool:
		return True

	def package(self):
		return "Emma Next-Turn Swap Lock"

	def assess(self, args={}):
		return self.generate_response(
			ResponseType.SKIP,
			{"msg": "Emma: this character cannot be swapped out this turn."},
		)


class Emma(AVGESupporterCard):
	_SELECTED_BENCH_KEY = "emma_selected_opponent_bench"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	@staticmethod
	def play_card(card_for: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
		from card_game.internal_events import InputEvent, TransferCard
		opponent = card_for.player.opponent

		opponent_active = opponent.get_active_card()
		opponent_bench = opponent.cardholders[Pile.BENCH]

		if(len(opponent_bench) == 0):
			return card_for.generate_response(ResponseType.SKIP, {"msg": "Opponent has no benched character to switch with."})

		def _input_valid(result) -> bool:
			return (
				len(result) == 1
				and isinstance(result[0], AVGECharacterCard)
				and result[0] in opponent_bench
			)

		missing = object()
		selected_bench = card_for.env.cache.get(card_for, Emma._SELECTED_BENCH_KEY, missing, one_look=True)
		if(selected_bench is missing):
			return card_for.generate_interrupt([InputEvent(
							card_for.player,
							[Emma._SELECTED_BENCH_KEY],
							InputType.DETERMINISTIC,
							_input_valid,
							ActionTypes.NONCHAR,
							card_for,
							{
								"query_label": "emma_opponent_bench_switch",
								"targets": list(opponent_bench)
							},
						)])
		locked_character = selected_bench

		card_for.add_listener(EmmaNextTurnSwapLockAssessor(card_for, locked_character, opponent, opponent.get_next_turn()))
		card_for.propose(
			[
				TransferCard(
					selected_bench,
					opponent_bench,
					opponent.cardholders[Pile.ACTIVE],
					ActionTypes.NONCHAR,
					card_for,
				),
				TransferCard(
					opponent_active,
					opponent.cardholders[Pile.ACTIVE],
					opponent_bench,
					ActionTypes.NONCHAR,
					card_for,
				),
			]
		)

		return card_for.generate_response(ResponseType.CORE)
