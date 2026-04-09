from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class FriedmanHallTurnBeginOverrideAssessor(AVGEAssessor):
	def __init__(self, owner_card: AVGEStadiumCard):
		super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, FriedmanHall), group=EngineGroup.EXTERNAL_PRECHECK_1)
		self.owner_card = owner_card

	def event_match(self, event):
		from card_game.internal_events import PhasePickCard
		return self.owner_card._is_active_stadium() and isinstance(event, PhasePickCard)

	def event_effect(self) -> bool:
		return True

	def update_status(self):
		if(not self.owner_card._is_active_stadium()):
			self.invalidate()
		
	def assess(self, args=None):
		from card_game.internal_events import InputEvent, Phase2, TransferCard, PhasePickCard, EmptyEvent

		event = self.attached_event
		assert isinstance(event, PhasePickCard)
		if(event.temp_cache.get(FriedmanHall._TURNBEGIN_OVERRIDE_FLAG, False)):
			return self.generate_response(ResponseType.FAST_FORWARD)

		active_player = event.player

		deck = active_player.cardholders[Pile.DECK]
		hand = active_player.cardholders[Pile.HAND]
		if(len(deck) < 2):
			active_player.env.winner = active_player.opponent
			return self.generate_response(ResponseType.GAME_END, {"winner": active_player.opponent, "reason": "not enough cards in deck for stadium effect"})

		top_two_cards = list(deck.peek_n(2))
		opponent = active_player.opponent
		chosen = self.owner_card.env.cache.get(self.owner_card, FriedmanHall._TURNBEGIN_PICK_KEY, None, one_look=True)
		if(chosen is None):
			return self.generate_response(
				ResponseType.INTERRUPT,
				{INTERRUPT_KEY: 
	 					[InputEvent(opponent, 
				   					[FriedmanHall._TURNBEGIN_PICK_KEY], 
									InputType.SELECTION, 
									lambda res: True, 
									ActionTypes.ENV, 
									self.owner_card, 
									{"query_label": "friedmanhall_turnbegin_pick", 
		  							"targets": top_two_cards,
									  "display": top_two_cards})]},
			)

		other = top_two_cards[1] if chosen == top_two_cards[0] else top_two_cards[0]
		event.temp_cache[FriedmanHall._TURNBEGIN_OVERRIDE_FLAG] = True
		self.propose(AVGEPacket([
				EmptyEvent(ActionTypes.NONCHAR, self.owner_card, response_data={
					REVEAL_KEY: top_two_cards
				}),
				TransferCard(chosen, deck, hand, ActionTypes.ENV, self.owner_card),
				TransferCard(other, deck, deck, ActionTypes.ENV, self.owner_card, random.randint(0, len(deck))),
				Phase2(active_player, ActionTypes.ENV, None),
			], AVGEEngineID(self.owner_card, ActionTypes.NONCHAR, FriedmanHall)))
		return self.generate_response(ResponseType.FAST_FORWARD)


class FriedmanHall(AVGEStadiumCard):
	_TURNBEGIN_PICK_KEY = "friedmanhall_turnbegin_pick"
	_TURNBEGIN_OVERRIDE_FLAG = "friedmanhall_turnbegin_override_done"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self) -> Response:
		self.add_listener(FriedmanHallTurnBeginOverrideAssessor(self))
		return self.generate_response()
