from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class Angel(AVGESupporterCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	@staticmethod
	def play_card(card: AVGECard) -> Response:
		from card_game.catalog.tools.AVGETShirt import AVGETShirt
		from card_game.internal_events import AVGECardStatusChange

		def generate_packet():
			player = card.player
			opponent = player.opponent

			packet = []
			for character in player.get_cards_in_play():
				packet.append(
						AVGECardStatusChange(
							StatusEffect.GOON,
							StatusChangeType.ADD,
							character,
							ActionTypes.NONCHAR,
							card,
						)
					)

			for character in opponent.get_cards_in_play():
				has_avget_shirt = any(isinstance(tool, AVGETShirt) for tool in character.tools_attached)
				if has_avget_shirt:
					continue

				packet.append(
					AVGECardStatusChange(
						StatusEffect.GOON,
						StatusChangeType.REMOVE,
						character,
						ActionTypes.NONCHAR,
						card,
					)
				)
			return packet	
		card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.NONCHAR, Angel)))

		return card.generate_response(ResponseType.CORE)
