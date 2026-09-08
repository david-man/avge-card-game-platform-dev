from __future__ import annotations

import random

from card_game.avge_abstracts import *

from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class ArrangerStatusReactor(AVGEReactor):
	_DECISION_KEY = "arranger_shuffle_decision"

	def __init__(self, env : AVGEEnvironment):
		super().__init__(
			identifier=AVGEEngineID(env, ActionTypes.ENV, None),
			group=EngineGroup.EXTERNAL_REACTORS,
		)
		self.env = env

	def _has_arranger(self, character: AVGECharacterCard | None) -> bool:
		if(not isinstance(character, AVGECharacterCard)):
			return False
		return len(character.statuses_attached.get(StatusEffect.ARRANGER, [])) > 0

	def _affected_character_from_event(self, event) -> AVGECharacterCard | None:
		from card_game.avge_abstracts.AVGECardholder import AVGEToolCardholder
		from card_game.internal_events import AVGECardHPChange, TransferCard

		if(isinstance(event, AVGECardHPChange)):
			if(event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE):
				return None
			if(isinstance(event.target_card, AVGECharacterCard)):
				return event.target_card
			return None

		if(isinstance(event, TransferCard)):
			if(not isinstance(event.card, AVGEToolCard)):
				return None
			if(event.pile_to.pile_type != Pile.DISCARD):
				return None
			if(not isinstance(event.pile_from, AVGEToolCardholder)):
				return None
			if(isinstance(event.pile_from.parent_card, AVGECharacterCard)):
				return event.pile_from.parent_card
			return None

		return None

	def event_match(self, event):
		return self._has_arranger(self._affected_character_from_event(event))

	def event_effect(self) -> bool:
		return self._has_arranger(self._affected_character_from_event(self.attached_event))

	def update_status(self):
		return

	def make_announcement(self) -> bool:
		return True

	def __str__(self):
		return "Arranger Status Reactor"

	def react(self, args={}):
		from card_game.internal_events import InputEvent

		event = self.attached_event
		affected_character = self._affected_character_from_event(event)

		if(not isinstance(affected_character, AVGECharacterCard)):
			return Response(ResponseType.ACCEPT, Data())

		discard = affected_character.player.cardholders[Pile.DISCARD]
		deck = affected_character.player.cardholders[Pile.DECK]
		if(len(discard) == 0):
			return Response(ResponseType.ACCEPT, Data())

		decision = affected_character.env.cache.get(affected_character, ArrangerStatusReactor._DECISION_KEY, None, one_look=True)
		if(decision is None):
			return Response(
				ResponseType.INTERRUPT,
				Interrupt[AVGEEvent]([
						InputEvent(
							affected_character.player,
							[ArrangerStatusReactor._DECISION_KEY],
							lambda r : True,
							ActionTypes.PASSIVE,
							affected_character,
							StrSelectionQuery('Arranger: Shuffle a random card from discard into deck?', ['Yes', 'No'], ['Yes', 'No'], False, False)
						)
					]),
			)

		if(not decision == 'Yes'):
			return Response(ResponseType.ACCEPT, Data())

		random_discard_card = random.choice(list(discard))
		p: PacketType = []
		p.append(
			TransferCard(
				random_discard_card,
				discard,
				deck,
				ActionTypes.PASSIVE,
				affected_character,
				RevealCards('Arranger: Shuffled a random discard card into the deck.', [affected_character.player.unique_id], default_timeout, [random_discard_card]),
				random.randint(0, len(deck)),
			)
		)
		self.propose(
			AVGEPacket(p, AVGEEngineID(self.env, ActionTypes.ENV, None))
		)
		return Response(ResponseType.ACCEPT, Data())
