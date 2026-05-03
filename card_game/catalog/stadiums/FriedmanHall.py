from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import EmptyEvent, InputEvent, Phase2, PhasePickCard, TransferCard


class FriedmanHallTurnBeginOverrideAssessor(AVGEAssessor):
	def __init__(self, owner_card: AVGEStadiumCard):
		super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, FriedmanHall), group=EngineGroup.EXTERNAL_PRECHECK_1)
		self.owner_card = owner_card

	def event_match(self, event):
		return self.owner_card._is_active_stadium() and isinstance(event, PhasePickCard)

	def event_effect(self) -> bool:
		return True

	def update_status(self):
		if(not self.owner_card._is_active_stadium()):
			self.invalidate()
		
	def assess(self, args=None):
		event = self.attached_event
		assert isinstance(event, PhasePickCard)
		if(event.temp_cache.get(FriedmanHall._TURNBEGIN_OVERRIDE_FLAG, False)):
			return Response(ResponseType.FAST_FORWARD, Data())

		active_player = event.env.player_turn

		deck = active_player.cardholders[Pile.DECK]
		hand = active_player.cardholders[Pile.HAND]
		if(len(deck) < 2):
			return Response(ResponseType.ACCEPT, Data())

		top_two_cards = list(deck.peek_n(2))
		opponent = active_player.opponent
		chosen = self.owner_card.env.cache.get(self.owner_card, FriedmanHall._TURNBEGIN_PICK_KEY, None, one_look=True)
		if(chosen is None):
			return Response(
				ResponseType.INTERRUPT,
				Interrupt[AVGEEvent]([InputEvent(
					opponent,
					[FriedmanHall._TURNBEGIN_PICK_KEY],
					lambda res: True,
					ActionTypes.ENV,
					self.owner_card,
					CardSelectionQuery('Friedman Hall: Opponent chooses one card for you to keep.', top_two_cards, top_two_cards, False, False)
				)]),
			)

		if chosen not in top_two_cards:
			raise Exception('FriedmanHall: Invalid turn-begin card selection')

		other = top_two_cards[1] if chosen == top_two_cards[0] else top_two_cards[0]
		event.temp_cache[FriedmanHall._TURNBEGIN_OVERRIDE_FLAG] = True
		packet: PacketType = []
		packet.extend([
			EmptyEvent(
				ActionTypes.NONCHAR,
				self.owner_card,
				ResponseType.CORE,
				RevealCards('Friedman Hall: Top 2 drawn cards', all_players, default_timeout, top_two_cards),
			),
			TransferCard(chosen, deck, hand, ActionTypes.ENV, self.owner_card, None),
			TransferCard(other, deck, hand, ActionTypes.ENV, self.owner_card, None),
			TransferCard(other, hand, deck, ActionTypes.ENV, self.owner_card, None, random.randint(0, len(deck))),
			Phase2(event.env, ActionTypes.ENV, event.env),
		])
		self.propose(AVGEPacket(packet, AVGEEngineID(self.owner_card, ActionTypes.NONCHAR, FriedmanHall)))
		return Response(ResponseType.FAST_FORWARD, Notify('Friedman Hall: Democratic Process', all_players, default_timeout))


class FriedmanHall(AVGEStadiumCard):
	_TURNBEGIN_PICK_KEY = "friedmanhall_turnbegin_pick"
	_TURNBEGIN_OVERRIDE_FLAG = "friedmanhall_turnbegin_override_done"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self) -> Response:
		self.add_listener(FriedmanHallTurnBeginOverrideAssessor(self))
		return Response(ResponseType.CORE, Data())
