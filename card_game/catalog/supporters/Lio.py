from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class Lio(AVGESupporterCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	@staticmethod
	def play_card(card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:
		from card_game.internal_events import TransferCard

		player = card.player
		def hand() -> PacketType:
			packet : PacketType= []
			for c in player.cardholders[Pile.HAND]:
				def gen(k=c) -> PacketType:
					return [TransferCard(
						k,
						player.cardholders[Pile.HAND],
						player.cardholders[Pile.DECK],
						ActionTypes.NONCHAR,
						card,
						random.randint(0, len(player.cardholders[Pile.DECK])),
					)]
				packet.append(
					gen
				)
			return packet

		def draw() -> PacketType:
			packet : PacketType= []
			deck = player.cardholders[Pile.DECK]
			for _ in range(4):
				def gen() -> PacketType:
					if(len(deck) == 0):
						return []
					return [TransferCard(
						deck.peek(),
						deck,
						player.cardholders[Pile.HAND],
						ActionTypes.NONCHAR,
						card)]
				packet.append(
					gen
				)
			return packet

		card.propose(AVGEPacket([hand, draw], AVGEEngineID(card, ActionTypes.NONCHAR, Lio)))

		return card.generate_response(ResponseType.CORE)
