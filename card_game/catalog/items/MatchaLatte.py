from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class MatchaLatte(AVGEItemCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card_for: AVGECharacterCard, parent_event: AVGEEvent, args: Data = None) -> Response:
		from card_game.internal_events import AVGECardHPChange
		def generate_packet():
			packet = []
			for card in card_for.player.get_cards_in_play():
				packet.append(
					AVGECardHPChange(
						card,
						10,
						AVGEAttributeModifier.ADDITIVE,
						card.card_type,
						ActionTypes.NONCHAR,
						card_for,
					)
				)
			return packet
		card_for.propose(generate_packet)
		return card_for.generate_response()
