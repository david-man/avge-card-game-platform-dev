from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes
from card_game.catalog.stadiums.PetterutiLounge import PetterutiLounge
class MatchaLatte(AVGEItemCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self, card) -> Response:
		from card_game.internal_events import AVGECardHPChange
		packet = []
		heal = 10
		if(len(card.env.stadium_cardholder) > 0 and isinstance(card.env.stadium_cardholder, PetterutiLounge)):
			heal = 20
		for c in card.player.get_cards_in_play():
			packet.append(
				AVGECardHPChange(
					c,
					heal,
					AVGEAttributeModifier.ADDITIVE,
					CardType.ALL,
					ActionTypes.NONCHAR,
					None,
					card,
				)
			)
		card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, MatchaLatte)))
		return self.generic_response(card)
