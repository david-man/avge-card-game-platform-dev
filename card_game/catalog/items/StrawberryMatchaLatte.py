from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class StrawberryMatchaLatte(AVGEItemCard):
	_HEAL_TARGET_KEY = "strawberry_matcha_latte_heal_target"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card) -> Response:
		from card_game.internal_events import AVGECardHPChange, InputEvent

		target = card.env.cache.get(card, StrawberryMatchaLatte._HEAL_TARGET_KEY, None, one_look=True)
		if(target is None):
			def _input_valid(result) -> bool:
				return (
					len(result) == 1
					and isinstance(result[0], AVGECharacterCard)
					and result[0] in card.player.get_cards_in_play()
				)

			return card.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							card.player,
							[StrawberryMatchaLatte._HEAL_TARGET_KEY],
							InputType.DETERMINISTIC,
							_input_valid,
							ActionTypes.NONCHAR,
							card,
							{
								"query_type": "strawberry_matcha_latte_query",
								'targets': card.player.get_cards_in_play()
							},
						)
					]
				},
			)

		card.propose(
			AVGEPacket([
				AVGECardHPChange(
					target,
					20,
					AVGEAttributeModifier.ADDITIVE,
					target.card_type,
					ActionTypes.NONCHAR,
					card,
				)
			], AVGEEngineID(card, ActionTypes.NONCHAR, StrawberryMatchaLatte))
		)
		return card.generate_response(ResponseType.CORE)
