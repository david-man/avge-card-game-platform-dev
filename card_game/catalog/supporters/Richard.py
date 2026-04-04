from __future__ import annotations

import random

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class Richard(AVGESupporterCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	@staticmethod
	def play_card(card_for: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
		from card_game.internal_events import TransferCard


		discard = card_for.player.cardholders[Pile.DISCARD]
		deck = card_for.player.cardholders[Pile.DECK]

		randomized_discard = list(discard)
		random.shuffle(randomized_discard)

		randomized_deck = list(deck)
		random.shuffle(randomized_deck)

		packet = []

		for card in randomized_discard:
			packet.append(
				TransferCard(
					card,
					discard,
					deck,
					ActionTypes.NONCHAR,
					card_for,
				)
			)

		for card in randomized_deck:
			packet.append(
				TransferCard(
					card,
					deck,
					discard,
					ActionTypes.NONCHAR,
					card_for,
				)
			)

		if(len(packet) > 0):
			card_for.propose(packet)

		return card_for.generate_response(ResponseType.CORE)
