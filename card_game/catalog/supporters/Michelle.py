from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class Michelle(AVGESupporterCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	@staticmethod
	def play_card(card: AVGECard) -> Response:
		from card_game.internal_events import TransferCard
		if(card.env.round_id == 0):
			return card.generate_response(
				ResponseType.SKIP,
				{MESSAGE_KEY: "Michelle cannot be played on the first turn."},
			)

		opponent = card.player.opponent
		opponent_hand = opponent.cardholders[Pile.HAND]
		opponent_deck = opponent.cardholders[Pile.DECK]

		hand_snapshot = list(opponent_hand)
		initial_deck_count = len(opponent_deck)
		
		def hand_shuffle() -> PacketType:
			packet : PacketType= []
			for card in opponent.cardholders[Pile.HAND]:
				def shuffle_card() -> PacketType:
					return [TransferCard(
						card,
						opponent_hand,
						opponent_deck,
						ActionTypes.NONCHAR,
						card,
						random.randint(0, len(opponent.cardholders[Pile.DECK])),
					)]
				packet.append(
					shuffle_card
				)
			return packet
		def pick() -> PacketType:
			if(len(opponent.cardholders[Pile.DECK]) == 0):
				return []
			else:
				return [
					TransferCard(
						opponent.cardholders[Pile.DECK].peek(),
						opponent_deck,
						opponent_hand,
						ActionTypes.NONCHAR,
						card,
					)
				]
		card.propose(AVGEPacket([hand_shuffle, pick], AVGEEngineID(card, ActionTypes.NONCHAR, Michelle)))

		return card.generate_response(ResponseType.CORE)
