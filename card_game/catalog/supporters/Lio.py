from __future__ import annotations

import random

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class Lio(AVGESupporterCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	@staticmethod
	def play_card(card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:
		from card_game.internal_events import TransferCardCreator

		player = card.player
		hand = player.cardholders[Pile.HAND]
		deck = player.cardholders[Pile.DECK]

		hand_snapshot = list(hand)
		packet = []

		for c in hand_snapshot:
			packet.append(
				TransferCardCreator(
					c,
					hand,
					deck,
					ActionTypes.NONCHAR,
					card,
					lambda: random.randint(0, len(player.cardholders[Pile.DECK])),
				)
			)

		draw_count = min(4, len(deck) + len(hand_snapshot))
		for _ in range(draw_count):
			packet.append(
				TransferCardCreator(
					lambda: player.cardholders[Pile.DECK].peek(),
					deck,
					hand,
					ActionTypes.NONCHAR,
					card,
				)
			)

		if(len(packet) > 0):
			card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, Lio)))

		return card.generate_response(ResponseType.CORE)
