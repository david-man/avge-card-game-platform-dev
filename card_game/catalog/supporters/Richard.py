from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class Richard(AVGESupporterCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	@staticmethod
	def play_card(card: AVGECard) -> Response:
		from card_game.internal_events import TransferCard


		discard = card.player.cardholders[Pile.DISCARD]
		deck = card.player.cardholders[Pile.DECK]

		randomized_discard = [d for d in list(discard)]
		random.shuffle(randomized_discard)

		randomized_deck = [d for d in list(deck)]
		random.shuffle(randomized_deck)

		packet = []

		for card in randomized_discard:
			packet.append(
				TransferCard(
					card,
					discard,
					deck,
					ActionTypes.NONCHAR,
					card,
				)
			)

		for card in randomized_deck:
			packet.append(
				TransferCard(
					card,
					deck,
					discard,
					ActionTypes.NONCHAR,
					card,
				)
			)

		if(len(packet) > 0):
			card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, Richard)))

		return card.generate_response(ResponseType.CORE)
