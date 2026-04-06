from __future__ import annotations

import random

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class ConcertRoster(AVGEItemCard):
	_TOP_PICK_KEY = "concertroster_top_pick"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card) -> Response:
		from card_game.internal_events import InputEvent, TransferCard, ReorderCardholder


		deck = card.player.cardholders[Pile.DECK]
		hand = card.player.cardholders[Pile.HAND]

		if(len(deck) == 0):
			return card.generate_response(ResponseType.SKIP, {"msg": "No cards in deck for ConcertRoster."})

		consider_count = min(3, len(deck))
		considered_cards = list(deck.peek_n(consider_count))
		pick_choices = [c for c in considered_cards if isinstance(c, AVGECharacterCard) or isinstance(c, AVGEStadiumCard)]

		if(len(pick_choices) == 0):
			return card.generate_response(ResponseType.FAST_FORWARD, {"msg": "No character or stadium in top of deck for ConcertRoster."})

		def _input_valid(result) -> bool:
			if(len(result) != 1):
				return False
			chosen = result[0]
			return chosen in pick_choices


		def _shuffled_current_order():
			order = list(deck.get_order())
			random.shuffle(order)
			return order

		picked_card = None
		missing = object()
		picked_card = card.env.cache.get(card, ConcertRoster._TOP_PICK_KEY, missing)
		if(picked_card is missing):
			return card.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							card.player,
							[ConcertRoster._TOP_PICK_KEY],
							InputType.DETERMINISTIC,
							_input_valid,
							ActionTypes.NONCHAR,
							card,
							{
								"query_label": "concert_roster_top_pick",
								"targets": pick_choices
							},
						)
					]
				},
			)
		packet = []
		assert picked_card is not None
		packet.append(
			TransferCard(
				picked_card,
				deck,
				hand,
				ActionTypes.NONCHAR,
				card,
			)
		)
		card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, ConcertRoster)))
		return card.generate_response()
