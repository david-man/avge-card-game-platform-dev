from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.catalog.stadiums.PetterutiLounge import PetterutiLounge
from card_game.constants import ActionTypes
class StrawberryMatchaLatte(AVGEItemCard):
	_HEAL_TARGET_KEY = "strawberry_matcha_latte_heal_target"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	@staticmethod
	def play_card(card) -> Response:
		from card_game.internal_events import AVGECardHPChange, InputEvent

		target = card.env.cache.get(card, StrawberryMatchaLatte._HEAL_TARGET_KEY, None, one_look=True)
		if(target is None):
			return card.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							card.player,
							[StrawberryMatchaLatte._HEAL_TARGET_KEY],
							InputType.SELECTION,
							lambda res: True,
							ActionTypes.NONCHAR,
							card,
							{
								LABEL_FLAG: "strawberry_matcha_latte_query",
								TARGETS_FLAG: card.player.get_cards_in_play(),
								DISPLAY_FLAG: card.player.get_cards_in_play()
							},
						)
					]
				},
			)
		
		heal = 20
		if(len(card.env.stadium_cardholder) > 0 and isinstance(card.env.stadium_cardholder, PetterutiLounge)):
			heal = 30

		card.propose(
			AVGEPacket([
				AVGECardHPChange(
					target,
					heal,
					AVGEAttributeModifier.ADDITIVE,
					CardType.ALL,
					ActionTypes.NONCHAR,
					card,
				)
			], AVGEEngineID(card, ActionTypes.NONCHAR, StrawberryMatchaLatte))
		)
		return card.generate_response(ResponseType.CORE)
