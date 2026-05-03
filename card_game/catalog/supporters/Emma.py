from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class EmmaNextTurnSwapLockAssessor(AVGEAssessor):
	def __init__(self, owner_card: AVGECard, locked_character: AVGECharacterCard, opponent: AVGEPlayer, round_active: int):
		super().__init__(
			identifier=AVGEEngineID(owner_card, ActionTypes.NONCHAR, Emma),
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
		if(event.card.env.round_id != self.round_active):
			return False
		return True

	def event_effect(self) -> bool:
		return True

	def update_status(self):
		if(self.locked_character.env.round_id > self.round_active):
			self.invalidate()

	def make_announcement(self) -> bool:
		return True

	def __str__(self):
		return "Emma Next-Turn Swap Lock"

	def assess(self, args=None):
		return Response(
			ResponseType.SKIP,
			Notify("Emma: this character cannot retreat this turn.", [self.opponent.unique_id], default_timeout),
		)


class Emma(AVGESupporterCard):
	_SELECTED_BENCH_KEY = "emma_selected_opponent_bench"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self, card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:
		from card_game.internal_events import InputEvent, TransferCard
		opponent = card.player.opponent

		opponent_active = opponent.get_active_card()
		opponent_bench = opponent.cardholders[Pile.BENCH]

		if(len(opponent_bench) == 0):
			return Response(
				ResponseType.SKIP,
				Notify("Opponent has no benched character to switch with.", [card.player.unique_id], default_timeout),
			)
		selected_bench = card.env.cache.get(card, Emma._SELECTED_BENCH_KEY, None, True)
		if(selected_bench is None):
			return Response(
				ResponseType.INTERRUPT,
				Interrupt[InputEvent]([
					InputEvent(
						card.player,
						[Emma._SELECTED_BENCH_KEY],
						lambda res: True,
						ActionTypes.NONCHAR,
						card,
						CardSelectionQuery("emma_opponent_bench_switch", list(opponent_bench), list(opponent_bench), False, False),
					)
				]),
			)
		assert isinstance(selected_bench, AVGECharacterCard)
		locked_character = selected_bench
		card.add_listener(EmmaNextTurnSwapLockAssessor(card, locked_character, opponent, opponent.get_next_turn()))
		packet: PacketType = [
			TransferCard(
				selected_bench,
				opponent_bench,
				opponent.cardholders[Pile.ACTIVE],
				ActionTypes.NONCHAR,
				card,
				None,
			),
			TransferCard(
				opponent_active,
				opponent.cardholders[Pile.ACTIVE],
				opponent_bench,
				ActionTypes.NONCHAR,
				card,
				None,
			),
		]
		card.propose(
			AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, Emma))
		)

		return self.generic_response(card)
