from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class Camera(AVGEItemCard):
	_DISCARD_PICK_KEY = "camera_discard_supporter_or_stadium_pick"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card) -> Response:
		from card_game.internal_events import InputEvent, TransferCard

		player = card.player
		target_discard = player.cardholders[Pile.DISCARD]
		deck = player.cardholders[Pile.DECK]

		eligible_cards = [
			c
			for c in target_discard
			if isinstance(c, AVGESupporterCard) or isinstance(c, AVGEStadiumCard)
		]

		if(len(eligible_cards) == 0):
			return card.generate_response()

		chosen = card.env.cache.get(card, Camera._DISCARD_PICK_KEY, None, one_look=True)
		if(chosen is None):
			return card.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							player,
							[Camera._DISCARD_PICK_KEY],
							InputType.SELECTION,
							lambda res : True,
							ActionTypes.NONCHAR,
							card,
							{
								"query_label": "camera_discard_pick",
								"targets":eligible_cards,
								"display": list(target_discard)
							},
						)
					]
				},
			)
		def gen() -> PacketType:
			return [TransferCard(
					chosen,
					target_discard,
					deck,
					ActionTypes.NONCHAR,
					card,
					random.randint(0, len(deck)),
				)]
		card.propose(
			AVGEPacket([
				gen
			], AVGEEngineID(card, ActionTypes.NONCHAR, Camera))
		)

		return card.generate_response()
