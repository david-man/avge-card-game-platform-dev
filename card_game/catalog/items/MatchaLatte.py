from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class MatchaLatte(AVGEItemCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card) -> Response:
		from card_game.internal_events import AVGECardHPChange
		packet = []
		for card in card.player.get_cards_in_play():
			packet.append(
				AVGECardHPChange(
					card,
					10,
					AVGEAttributeModifier.ADDITIVE,
					card.card_type,
					ActionTypes.NONCHAR,
					card,
				)
			)
		card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, MatchaLatte)))
		return card.generate_response()
