from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class Richard(AVGESupporterCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self, card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:
		from card_game.internal_events import TransferCard


		discard = card.player.cardholders[Pile.DISCARD]
		deck = card.player.cardholders[Pile.DECK]

		randomized_discard = [d for d in list(discard)]
		random.shuffle(randomized_discard)

		randomized_deck = [d for d in list(deck)]
		random.shuffle(randomized_deck)

		packet: PacketType = []

		for moved_card in randomized_discard:
			packet.append(
				TransferCard(
					moved_card,
					discard,
					deck,
					ActionTypes.NONCHAR,
					card,
					None,
				)
			)

		for moved_card in randomized_deck:
			packet.append(
				TransferCard(
					moved_card,
					deck,
					discard,
					ActionTypes.NONCHAR,
					card,
					None,
				)
			)

		if(len(packet) > 0):
			card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, Richard)))

		return self.generic_response(card)
