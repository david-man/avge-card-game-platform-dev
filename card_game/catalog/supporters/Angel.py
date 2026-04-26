from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import AVGECardStatusChange, TransferCard

class Angel(AVGESupporterCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self, card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:

		def generate_packet() -> PacketType:
			player = card.player
			opponent = player.opponent
			opponent_discard = opponent.cardholders[Pile.DISCARD]

			packet: PacketType = []
			for character in player.get_cards_in_play():
				if not isinstance(character, AVGECharacterCard):
					continue
				packet.append(
						AVGECardStatusChange(
							StatusEffect.GOON,
							StatusChangeType.ADD,
							character,
							ActionTypes.NONCHAR,
							card,
							None,
						)
					)

			for character in opponent.get_cards_in_play():
				if not isinstance(character, AVGECharacterCard):
					continue
				for tool in list(character.tools_attached):
					packet.append(
						TransferCard(
							tool,
							character.tools_attached,
							opponent_discard,
							ActionTypes.NONCHAR,
							card,
							None,
						)
					)
			return packet	
		card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.NONCHAR, Angel)))

		return self.generic_response(card)
