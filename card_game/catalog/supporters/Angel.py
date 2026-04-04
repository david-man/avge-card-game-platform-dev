from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class Angel(AVGESupporterCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	@staticmethod
	def play_card(card_for: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
		from card_game.catalog.tools.AVGETShirt import AVGETShirt
		from card_game.internal_events import AVGEStatusChange

		def generate_packet():
			player = card_for.player
			opponent = player.opponent

			packet = []

			for character in player.get_cards_in_play():
				packet.append(
						AVGEStatusChange(
							character,
							StatusEffect.GOON,
							StatusChangeType.ADD,
							ActionTypes.NONCHAR,
							card_for,
						)
					)

			for character in opponent.get_cards_in_play():
				has_avget_shirt = any(isinstance(tool, AVGETShirt) for tool in character.tools_attached)
				if has_avget_shirt:
					continue

				packet.append(
					AVGEStatusChange(
						character,
						StatusEffect.GOON,
						StatusChangeType.REMOVE,
						ActionTypes.NONCHAR,
						card_for,
					)
				)
			return packet
		card_for.propose(generate_packet)

		return card_for.generate_response(ResponseType.CORE)
