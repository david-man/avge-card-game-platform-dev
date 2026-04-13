from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class Michelle(AVGESupporterCard):
	_KEEP_KEY = "michelle_keep_card"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	@staticmethod
	def play_card(card: AVGECard) -> Response:
		from card_game.internal_events import InputEvent, TransferCard

		if(card.env.round_id == 0):
			return card.generate_response(
				ResponseType.SKIP,
				{MESSAGE_KEY: "Michelle cannot be played on the first turn."},
			)

		opponent = card.player.opponent
		opponent_hand = opponent.cardholders[Pile.HAND]
		opponent_discard = opponent.cardholders[Pile.DISCARD]

		if(len(opponent_hand) <= 1):
			return card.generate_response(ResponseType.CORE)

		missing = object()
		keep_card = card.env.cache.get(card, Michelle._KEEP_KEY, missing, True)
		if(keep_card is missing):
			return card.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							opponent,
							[Michelle._KEEP_KEY],
							InputType.SELECTION,
							lambda r: True,
							ActionTypes.NONCHAR,
							card,
							{
								LABEL_FLAG: "michelle_opponent_keep_one",
								TARGETS_FLAG: list(opponent_hand),
								DISPLAY_FLAG: list(opponent_hand),
							},
						)
					]
				},
			)

		packet: PacketType = []
		for hand_card in list(opponent_hand):
			if(hand_card == keep_card):
				continue
			packet.append(
				TransferCard(
					hand_card,
					opponent_hand,
					opponent_discard,
					ActionTypes.NONCHAR,
					card,
					random.randint(0, len(opponent_discard)),
				)
			)

		if(len(packet) > 0):
			card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, Michelle)))
		card.env.cache.delete(card, Michelle._KEEP_KEY)

		return card.generate_response(ResponseType.CORE)
