from __future__ import annotations

import random

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class Lio(AVGESupporterCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	@staticmethod
	def play_card(card_for: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
		from card_game.internal_events import TransferCard

		player = card_for.player
		hand = player.cardholders[Pile.HAND]
		deck = player.cardholders[Pile.DECK]

		hand_snapshot = list(hand)
		packet = []

		for card in hand_snapshot:
			packet.append(
				TransferCard(
					card,
					hand,
					deck,
					ActionTypes.NONCHAR,
					card_for,
					lambda: random.randint(0, len(player.cardholders[Pile.DECK])),
				)
			)

		draw_count = min(4, len(deck) + len(hand_snapshot))
		for _ in range(draw_count):
			packet.append(
				TransferCard(
					lambda: player.cardholders[Pile.DECK].peek(),
					deck,
					hand,
					ActionTypes.NONCHAR,
					card_for,
				)
			)

		if(len(packet) > 0):
			card_for.propose(packet)

		return card_for.generate_response(ResponseType.CORE)
