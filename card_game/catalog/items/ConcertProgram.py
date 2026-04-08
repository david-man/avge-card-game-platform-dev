from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes


class ConcertProgram(AVGEItemCard):
	_TOP_CHARACTER_PICK_KEY = "concertprogram_top_character_pick"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card) -> Response:
		from card_game.internal_events import InputEvent, TransferCard, ReorderCardholder, EmptyEvent

		deck = card.player.cardholders[Pile.DECK]
		hand = card.player.cardholders[Pile.HAND]

		if(len(deck) == 0):
			return card.generate_response(ResponseType.SKIP, {MESSAGE_KEY: "No cards in deck for ConcertProgram."})

		consider_count = min(5, len(deck))
		considered_cards = list(deck.peek_n(consider_count))
		character_choices = [c for c in considered_cards if isinstance(c, AVGECharacterCard)]

		missing = object()
		picked_character = card.env.cache.get(card, ConcertProgram._TOP_CHARACTER_PICK_KEY, missing, one_look=True)
		if(picked_character is missing):
			return card.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							card.player,
							[ConcertProgram._TOP_CHARACTER_PICK_KEY],
							InputType.SELECTION,
							lambda r : True,
							ActionTypes.NONCHAR,
							card,
							{
								"query_label": "concert_program_top_pick",
								"targets": character_choices,
								"display": considered_cards,
								"allow_none": True
							},
						)
					]
				},
			)
		packet : PacketType = []
		
		if(picked_character is not None):
			packet.append(EmptyEvent(
					ActionTypes.NONCHAR,
					card,
					response_data={
						REVEAL_KEY: list(picked_character)
					}
				))
			packet.append(
				TransferCard(
					picked_character,
					deck,
					hand,
					ActionTypes.NONCHAR,
					card,
				)
			)
		def gen() -> PacketType:
			return[
				ReorderCardholder(
					deck,
					[c.unique_id for c in random.sample(list(deck), len(deck))],
					ActionTypes.NONCHAR,
					card,
				)
			]
		packet.append(gen)

		card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, ConcertProgram)))
		return card.generate_response()
