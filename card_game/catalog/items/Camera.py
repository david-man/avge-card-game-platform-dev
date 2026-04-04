from __future__ import annotations

import random

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class Camera(AVGEItemCard):
	_DISCARD_PICK_KEY = "camera_discard_supporter_or_stadium_pick"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card_for: AVGECharacterCard, parent_event: AVGEEvent, args: Data = None) -> Response:
		from card_game.internal_events import InputEvent, TransferCard

		player = card_for.player
		target_discard = player.cardholders[Pile.DISCARD]
		deck = player.cardholders[Pile.DECK]

		eligible_cards = [
			c
			for c in target_discard
			if isinstance(c, AVGESupporterCard) or isinstance(c, AVGEStadiumCard)
		]

		if(len(eligible_cards) == 0):
			return card_for.generate_response()

		def _input_valid(result) -> bool:
			if(len(result) != 1):
				return False
			chosen = result[0]
			return chosen in eligible_cards

		chosen = card_for.env.cache.get(card_for, Camera._DISCARD_PICK_KEY, None, one_look=True)
		if(chosen is None):
			return card_for.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							player,
							[Camera._DISCARD_PICK_KEY],
							InputType.DETERMINISTIC,
							_input_valid,
							ActionTypes.NONCHAR,
							card_for,
							{
								"query_label": "camera_discard_pick",
								"targets":eligible_cards,
							},
						)
					]
				},
			)

		card_for.propose(
			TransferCard(
				chosen,
				target_discard,
				deck,
				ActionTypes.NONCHAR,
				card_for,
				lambda: random.randint(0, len(deck)),
			)
		)

		return card_for.generate_response()
