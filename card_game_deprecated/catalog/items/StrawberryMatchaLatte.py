from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.catalog.stadiums.PetterutiLounge import PetterutiLounge
from card_game.internal_events import AVGECardHPChange, InputEvent


class StrawberryMatchaLatte(AVGEItemCard):
	_HEAL_TARGET_KEY = 'strawberry_matcha_latte_heal_target'

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self, card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:
		targets = [c for c in card.player.get_cards_in_play() if isinstance(c, AVGECharacterCard)]

		missing = object()
		target = card.env.cache.get(card, StrawberryMatchaLatte._HEAL_TARGET_KEY, missing, one_look=True)
		if target is missing:
			return Response(
				ResponseType.INTERRUPT,
				Interrupt[AVGEEvent]([
						InputEvent(
							card.player,
							[StrawberryMatchaLatte._HEAL_TARGET_KEY],
							lambda res: True,
							ActionTypes.NONCHAR,
							card,
							CardSelectionQuery('Strawberry Matcha Latte: Choose one of your characters to heal.', targets, targets, False, False)
						)
					]),
			)

		if not isinstance(target, AVGECharacterCard) or target not in targets:
			raise Exception('StrawberryMatchaLatte: Invalid heal target selection')
		
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
					None,
					card,
				)
			], AVGEEngineID(card, ActionTypes.NONCHAR, StrawberryMatchaLatte))
		)
		return self.generic_response(card)
