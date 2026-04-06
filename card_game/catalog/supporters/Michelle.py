from __future__ import annotations

import random

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class Michelle(AVGESupporterCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	@staticmethod
	def play_card(card: AVGECard) -> Response:
		from card_game.internal_events import TransferCardCreator
		if(card.env.round_id == 0):
			return card.generate_response(
				ResponseType.SKIP,
				{"msg": "Michelle cannot be played on the first turn."},
			)

		opponent = card.player.opponent
		opponent_hand = opponent.cardholders[Pile.HAND]
		opponent_deck = opponent.cardholders[Pile.DECK]

		hand_snapshot = list(opponent_hand)
		initial_deck_count = len(opponent_deck)
		packet = []

		for card in hand_snapshot:
			packet.append(
				TransferCardCreator(
					card,
					opponent_hand,
					opponent_deck,
					ActionTypes.NONCHAR,
					card,
					lambda: random.randint(0, len(opponent.cardholders[Pile.DECK])),
				)
			)

		if(initial_deck_count + len(hand_snapshot) > 0):
			packet.append(
				TransferCardCreator(
					lambda : opponent.cardholders[Pile.DECK].peek(),
					opponent_deck,
					opponent_hand,
					ActionTypes.NONCHAR,
					card,
				)
			)

		if(len(packet) > 0):
			card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, Michelle)))

		return card.generate_response(ResponseType.CORE)
