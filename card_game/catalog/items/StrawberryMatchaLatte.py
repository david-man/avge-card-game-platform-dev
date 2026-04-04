from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class StrawberryMatchaLatte(AVGEItemCard):
	_HEAL_TARGET_KEY = "strawberry_matcha_latte_heal_target"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card_for: AVGECharacterCard, parent_event: AVGEEvent, args: Data = None) -> Response:
		from card_game.internal_events import AVGECardHPChange, InputEvent

		target = card_for.env.cache.get(card_for, StrawberryMatchaLatte._HEAL_TARGET_KEY, None, one_look=True)
		if(target is None):
			def _input_valid(result) -> bool:
				return (
					len(result) == 1
					and isinstance(result[0], AVGECharacterCard)
					and result[0] in card_for.player.get_cards_in_play()
				)

			return card_for.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							card_for.player,
							[StrawberryMatchaLatte._HEAL_TARGET_KEY],
							InputType.DETERMINISTIC,
							_input_valid,
							ActionTypes.NONCHAR,
							card_for,
							{
								"query_type": "strawberry_matcha_latte_query",
								'targets': card_for.player.get_cards_in_play()
							},
						)
					]
				},
			)

		card_for.propose(
			AVGECardHPChange(
				target,
				20,
				AVGEAttributeModifier.ADDITIVE,
				target.card_type,
				ActionTypes.NONCHAR,
				card_for,
			)
		)
		return card_for.generate_response(ResponseType.CORE)
