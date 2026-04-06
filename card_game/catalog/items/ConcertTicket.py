from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class ConcertTicket(AVGEItemCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card) -> Response:
		from card_game.internal_events import TransferCardCreator

		hand = card.player.cardholders[Pile.HAND]
		deck = card.player.cardholders[Pile.DECK]

		current_hand_size = len(hand)

		if(current_hand_size == 1):
			return card.generate_response(ResponseType.SKIP, {"msg": "ConcertTicket cannot be played as the only card in hand."})

		if(current_hand_size >= 4):
			return card.generate_response(ResponseType.SKIP, {"msg": "ConcertTicket cannot be played when hand size is already 3 or more."})

		draw_needed = 4 - current_hand_size
		draw_count = min(draw_needed, len(deck))
		packet = []
		for _ in range(draw_count):
			packet.append(
				TransferCardCreator(
					lambda: deck.peek(),
					deck,
					hand,
					ActionTypes.NONCHAR,
					card,
				)
			)

		card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, ConcertTicket)))
		return card.generate_response()
