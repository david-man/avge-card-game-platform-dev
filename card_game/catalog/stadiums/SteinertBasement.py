from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import PhasePickCard, PlayCharacterCard, TransferCard

class SteinertBasementTwoInPlayBonusDrawReactor(AVGEReactor):
	def __init__(self, owner_card: AVGEStadiumCard):
		super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, SteinertBasement), group=EngineGroup.EXTERNAL_REACTORS)
		self.owner_card = owner_card

	def event_match(self, event):
		if(not isinstance(event, PhasePickCard)):
			return False
		player = event.env.player_turn
		return self.owner_card._is_active_stadium() and len(player.get_cards_in_play()) == 2

	def event_effect(self) -> bool:
		return True

	def update_status(self):
		if(not self.owner_card._is_active_stadium()):
			self.invalidate()

	def make_announcement(self) -> bool:
		return True

	def package(self):
		return "SteinertBasement Duo Queue"

	def react(self, args=None):
		event = self.attached_event
		assert isinstance(event, PhasePickCard)
		player : AVGEPlayer = event.env.player_turn
		deck = player.cardholders[Pile.DECK]
		hand = player.cardholders[Pile.HAND]
		if(len(deck) == 0):
			return Response(ResponseType.ACCEPT, Notify('Steinert Basement: No extra card available for Duo Queue.', [player.unique_id], default_timeout))

		self.propose(AVGEPacket([
			TransferCard(deck.peek(), deck, hand, ActionTypes.ENV, self.owner_card, None)
		], AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, SteinertBasement)))
		return Response(ResponseType.ACCEPT, Notify('Steinert Basement: Duo Queue grants one additional draw this turn.', [player.unique_id], default_timeout))


class SteinertBasementAttackExtraCostAssessor(AVGEModifier):
	def __init__(self, owner_card: AVGEStadiumCard):
		super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, SteinertBasement), group=EngineGroup.EXTERNAL_MODIFIERS_1)
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

	def modify(self, args=None):
		assert isinstance(self.attached_event, PlayCharacterCard)
		event : PlayCharacterCard = self.attached_event
		event.energy_requirement += 1
		return Response(ResponseType.ACCEPT, Notify("Steinert Basement: Attack cost increased by 1", all_players, default_timeout))


class SteinertBasement(AVGEStadiumCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self) -> Response:
		self.add_listener(SteinertBasementTwoInPlayBonusDrawReactor(self))
		self.add_listener(SteinertBasementAttackExtraCostAssessor(self))
		return Response(ResponseType.CORE, Data())
