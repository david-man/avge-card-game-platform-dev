from __future__ import annotations

import random

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class ConcertProgram(AVGEItemCard):
	_TOP_CHARACTER_PICK_KEY = "concertprogram_top_character_pick"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card) -> Response:
		from card_game.internal_events import InputEvent, TransferCard, ReorderCardholderCreator

		deck = card.player.cardholders[Pile.DECK]
		hand = card.player.cardholders[Pile.HAND]

		if(len(deck) == 0):
			return card.generate_response(ResponseType.SKIP, {"msg": "No cards in deck for ConcertProgram."})

		consider_count = min(5, len(deck))
		considered_cards = list(deck.peek_n(consider_count))
		character_choices = [c for c in considered_cards if isinstance(c, AVGECharacterCard)]

		if(len(character_choices) == 0):
			return card.generate_response()

		def _input_valid(result) -> bool:
			if(len(result) != 1):
				return False
			chosen = result[0]
			if(chosen is None):
				return True
			return isinstance(chosen, AVGECharacterCard) and chosen in character_choices


		picked_character = card.env.cache.get(card, ConcertProgram._TOP_CHARACTER_PICK_KEY, None, one_look=True)
		if(picked_character is None):
			return card.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							card.player,
							[ConcertProgram._TOP_CHARACTER_PICK_KEY],
							InputType.DETERMINISTIC,
							_input_valid,
							ActionTypes.NONCHAR,
							card,
							{
								"query_label": "concert_program_top_pick",
								"targets": considered_cards,
							},
						)
					]
				},
			)

		packet = []
		packet.append(
			TransferCard(
				picked_character,
				deck,
				hand,
				ActionTypes.NONCHAR,
				card,
			)
		)
		packet.append(
			ReorderCardholderCreator(
				deck,
				lambda : [c.unique_id for c in random.sample(list(deck), len(deck))],
				ActionTypes.NONCHAR,
				card,
			)
		)

		card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, ConcertProgram)))
		return card.generate_response()
