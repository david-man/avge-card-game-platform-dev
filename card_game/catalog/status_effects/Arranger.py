from __future__ import annotations

import random

from card_game.avge_abstracts import *

from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class ArrangerStatusReactor(AVGEReactor):
	_DECISION_KEY = "arranger_shuffle_decision"

	def __init__(self):
		super().__init__(
			identifier=AVGEEngineID(None, ActionTypes.ENV, None),
			group=EngineGroup.EXTERNAL_REACTORS,
		)

	def _has_arranger(self, character: AVGECharacterCard | None) -> bool:
		if(not isinstance(character, AVGECharacterCard)):
			return False
		return len(character.statuses_attached.get(StatusEffect.ARRANGER, [])) > 0

	def event_match(self, event):
		from card_game.avge_abstracts.AVGECardholder import AVGEToolCardholder
		from card_game.internal_events import AVGECardHPChange, TransferCard

		if(isinstance(event, AVGECardHPChange)):
			if(event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE):
				return False
			return self._has_arranger(event.target_card)

		if(isinstance(event, TransferCard)):
			if(not isinstance(event.card, AVGEToolCard)):
				return False
			if(event.pile_to.pile_type != Pile.DISCARD):
				return False
			if(not isinstance(event.pile_from, AVGEToolCardholder)):
				return False
			return self._has_arranger(event.pile_from.parent_card)

		return False

	def event_effect(self) -> bool:
		return True

	def update_status(self):
		return

	def make_announcement(self) -> bool:
		return True

	def package(self):
		return "Arranger Status Reactor"

	def react(self, args={}):
		from card_game.avge_abstracts.AVGECardholder import AVGEToolCardholder
		from card_game.internal_events import AVGECardHPChange, InputEvent, TransferCard

		event = self.attached_event
		affected_character = None

		if(isinstance(event, AVGECardHPChange)):
			affected_character = event.target_card
		elif(isinstance(event, TransferCard) and isinstance(event.pile_from, AVGEToolCardholder)):
			affected_character = event.pile_from.parent_card

		if(not isinstance(affected_character, AVGECharacterCard)):
			return self.generate_response()

		discard = affected_character.player.cardholders[Pile.DISCARD]
		deck = affected_character.player.cardholders[Pile.DECK]
		if(len(discard) == 0):
			return self.generate_response()

		decision = affected_character.env.cache.get(affected_character, ArrangerStatusReactor._DECISION_KEY, None, one_look=True)
		if(decision is None):
			return self.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							affected_character.player,
							[ArrangerStatusReactor._DECISION_KEY],
							InputType.BINARY,
							lambda r : True,
							ActionTypes.PASSIVE,
							affected_character,
							{
								"query_label": "arranger_optional_shuffle",
							},
						)
					]
				},
			)

		if(not decision):
			return self.generate_response()

		random_discard_card = random.choice(list(discard))
		p : PacketType = [TransferCard(
				random_discard_card,
				discard,
				deck,
				ActionTypes.PASSIVE,
				affected_character,
				random.randint(0, len(deck)),
			)]
		self.propose(
			AVGEPacket(p, AVGEEngineID(None, ActionTypes.ENV, None))
		)
		return self.generate_response()
