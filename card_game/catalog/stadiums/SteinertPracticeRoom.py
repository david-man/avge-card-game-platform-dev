from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup

from card_game.internal_events import TransferCard, PlayCharacterCard
class SteinertPracticeRoomBenchCapAssessor(AVGEAssessor):
	def __init__(self, owner_card: AVGEStadiumCard):
		super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, SteinertPracticeRoom), group=EngineGroup.EXTERNAL_PRECHECK_1)
		self.owner_card = owner_card

	def event_match(self, event):
		
		if(not self.owner_card._is_active_stadium()):
			return False
		if(not isinstance(event, TransferCard)):
			return False
		if(not event.catalyst_action == ActionTypes.PLAYER_CHOICE):
			return False
		if(event.pile_to.pile_type != Pile.BENCH):
			return False
		if(len(event.pile_to) < 2):
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
		return "SteinertPracticeRoom BenchCap"

	def assess(self, args=None):
		return self.generate_response(ResponseType.SKIP, {MESSAGE_KEY: "SteinertPracticeRoom: cannot have more than 2 benched characters."})


class SteinertPracticeRoomAttackExtraCostAssessor(AVGEModifier):
	def __init__(self, owner_card: AVGEStadiumCard):
		super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, SteinertPracticeRoom), group=EngineGroup.EXTERNAL_MODIFIERS_1)
		self.owner_card = owner_card

	def event_match(self, event):
		from card_game.internal_events import PlayCharacterCard
		if(not self.owner_card._is_active_stadium()):
			return False
		if(not isinstance(event, PlayCharacterCard)):
			return False
		if(event.card_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]):
			return False
		if(not isinstance(event.card, AVGECharacterCard)):
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
		return "SteinertPracticeRoom 15 minutes"

	def modify(self, args=None):
		assert isinstance(self.attached_event, PlayCharacterCard)
		event : PlayCharacterCard = self.attached_event
		event.energy_requirement += 1
		return self.generate_response()


class SteinertPracticeRoom(AVGEStadiumCard):
	_OWNER_BENCH_DISCARD_KEY = "steinertpractice_owner_bench_discard"
	_OPP_BENCH_DISCARD_KEY = "steinertpractice_opp_bench_discard"
	_OWNER_RESOLVED_KEY = "steinertpractice_owner_resolved"
	_OPP_RESOLVED_KEY = "steinertpractice_opp_resolved"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self) -> Response:
		from card_game.internal_events import InputEvent, PlayCharacterCard, TransferCard
		player = self.original_owner
		assert player is not None
		def _resolve_discards_for_player(target_player: AVGEPlayer, base_key: str, resolved_key: str) -> Response:

			if(bool(self.env.cache.get(self, resolved_key, False))):
				return self.generate_response(ResponseType.CORE)

			bench = target_player.cardholders[Pile.BENCH]
			discard = target_player.cardholders[Pile.DISCARD]
			extra = max(0, len(bench) - 2)
			if(extra == 0):
				self.env.cache.set(self, resolved_key, True)
				self.env.cache.delete(self, base_key)
				return self.generate_response(ResponseType.CORE)

			keys = [base_key + str(i) for i in range(extra)]
			chosen = [self.env.cache.get(self, key, None, True) for key in keys]
			if(chosen[0] is None):
				return self.generate_response(
					ResponseType.INTERRUPT,
					{
						INTERRUPT_KEY: [
							InputEvent(
								target_player,
								keys,
								InputType.SELECTION,
								lambda res: True,
								ActionTypes.NONCHAR,
								self,
								{
									"query_label": "Steinert-practice-room-bench",
									"targets": list(target_player.cardholders[Pile.BENCH]),
									"display": list(target_player.cardholders[Pile.BENCH])
								},
							)
						]
					},
				)

			packet = []
			for card in chosen:
				assert isinstance(card, AVGECharacterCard)
				packet.append(
					TransferCard(
						card,
						bench,
						discard,
						ActionTypes.NONCHAR,
						self,
					)
				)

			self.env.cache.set(self, resolved_key, True)
			if(len(packet) > 0):
				return self.generate_response(ResponseType.INTERRUPT, {INTERRUPT_KEY: packet})
			return self.generate_response(ResponseType.CORE)
		
		owner_resolve = _resolve_discards_for_player(
			player,
			SteinertPracticeRoom._OWNER_BENCH_DISCARD_KEY,
			SteinertPracticeRoom._OWNER_RESOLVED_KEY,
		)
		if(owner_resolve.response_type == ResponseType.INTERRUPT):
			return owner_resolve

		opponent_resolve = _resolve_discards_for_player(
			player.opponent,
			SteinertPracticeRoom._OPP_BENCH_DISCARD_KEY,
			SteinertPracticeRoom._OPP_RESOLVED_KEY,
		)
		if(opponent_resolve.response_type == ResponseType.INTERRUPT):
			return opponent_resolve

		self.env.cache.delete(self, SteinertPracticeRoom._OWNER_RESOLVED_KEY)
		self.env.cache.delete(self, SteinertPracticeRoom._OPP_RESOLVED_KEY)

		self.add_listener(SteinertPracticeRoomBenchCapAssessor(self))
		self.add_listener(SteinertPracticeRoomAttackExtraCostAssessor(self))

		return self.generate_response()
