from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import TransferCard


class ConcertTicket(AVGEItemCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self, card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:
		hand = card.player.cardholders[Pile.HAND]
		deck = card.player.cardholders[Pile.DECK]

		current_hand_size = len(hand)

		if(current_hand_size == 1):
			return Response(
				ResponseType.SKIP,
				Notify('ConcertTicket cannot be played as the only card in hand.', [card.player.unique_id], default_timeout)
			)

		draw_needed = max(0, 4 - current_hand_size)
		draw_count = min(draw_needed, len(deck))

		def draw_one() -> PacketType:
			if len(deck) == 0:
				return []
			return [TransferCard(
				deck.peek(),
				deck,
				hand,
				ActionTypes.NONCHAR,
				card,
				None,
			)]

		if draw_count > 0:
			card.propose(
				AVGEPacket([draw_one] * draw_count, AVGEEngineID(card, ActionTypes.NONCHAR, ConcertTicket))
			)

		return self.generic_response(card)
