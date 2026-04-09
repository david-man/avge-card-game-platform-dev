from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *

from card_game.constants import ActionTypes
class ConcertTicket(AVGEItemCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card) -> Response:
		from card_game.internal_events import TransferCard

		hand = card.player.cardholders[Pile.HAND]
		deck = card.player.cardholders[Pile.DECK]

		current_hand_size = len(hand)

		if(current_hand_size == 1):
			return card.generate_response(ResponseType.SKIP, {MESSAGE_KEY: "ConcertTicket cannot be played as the only card in hand."})

		if(current_hand_size >= 4):
			return card.generate_response(ResponseType.SKIP, {MESSAGE_KEY: "ConcertTicket cannot be played when hand size is already 3 or more."})
		def gen_all() -> PacketType:
			draw_needed = 4 - current_hand_size
			draw_count = min(draw_needed, len(deck))
			def gen() -> PacketType:
				packet = []
				if(len(deck) == 3):
					return []
				else:
					return [TransferCard(
							deck.peek(),
							deck,
							hand,
							ActionTypes.NONCHAR,
							card,
						)]
			return [gen] * draw_count
		
		card.propose(AVGEPacket([gen_all], AVGEEngineID(card, ActionTypes.NONCHAR, ConcertTicket)))
		return card.generate_response()
