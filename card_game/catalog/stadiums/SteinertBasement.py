from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import PlayCharacterCard

class SteinertBasementTwoInPlayBonusDrawReactor(AVGEReactor):
	def __init__(self, owner_card: AVGEStadiumCard):
		super().__init__(identifier=(owner_card, AVGEEventListenerType.PASSIVE), group=EngineGroup.EXTERNAL_REACTORS)
		self.owner_card = owner_card

	def event_match(self, event):
		from card_game.internal_events import PhasePickCard

		if(not isinstance(event, PhasePickCard)):
			return False
		player = event.player
		return self.owner_card._is_active_stadium() and len(player.get_cards_in_play()) == 2

	def event_effect(self) -> bool:
		return True

	def update_status(self):
		if(not self.owner_card._is_active_stadium()):
			self.invalidate()

	def make_announcement(self) -> bool:
		return True

	def package(self):
		return "SteinertBasement Reactor"

	def react(self, args={}):
		from card_game.internal_events import TransferCard

		event = self.attached_event
		player : AVGEPlayer = event.player
		deck = player.cardholders[Pile.DECK]
		hand = player.cardholders[Pile.HAND]
		if(len(deck) == 0):
			player.env.winner = player.opponent
			return self.generate_response(ResponseType.GAME_END, {"winner": player.opponent, "reason": "steinert basement extra draw failed"})

		self.propose(TransferCard(deck.peek(), deck, hand, ActionTypes.ENV, self.owner_card))
		return self.generate_response()


class SteinertBasementAttackExtraCostAssessor(AVGEModifier):
	def __init__(self, owner_card: AVGEStadiumCard):
		super().__init__(identifier=(owner_card, AVGEEventListenerType.PASSIVE), group=EngineGroup.EXTERNAL_MODIFIERS_2)
		self.owner_card = owner_card

	def event_match(self, event):
		

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
		return True

	def event_effect(self) -> bool:
		return True

	def update_status(self):
		if(not self.owner_card._is_active_stadium()):
			self.invalidate()

	def make_announcement(self) -> bool:
		return True

	def package(self):
		return "SteinertBasement AttackCost"

	def modify(self, args={}):
		event : PlayCharacterCard = self.attached_event
		event.energy_requirement += 1
		return self.generate_response()


class SteinertBasement(AVGEStadiumCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self, parent_event: AVGEEvent) -> Response:
		self.add_listener(SteinertBasementTwoInPlayBonusDrawReactor(self))
		self.add_listener(SteinertBasementAttackExtraCostAssessor(self))
		return self.generate_response()
