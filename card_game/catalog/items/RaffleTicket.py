from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class RaffleTicket(AVGEItemCard):
	_HEAL_TARGET_KEY = "raffleticket_heal_target"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card_for: AVGECharacterCard, parent_event: AVGEEvent, args: Data = None) -> Response:
		from card_game.catalog.items.AVGEBirb import AVGEBirb
		from card_game.internal_events import AVGECardHPChange, InputEvent, TransferCard
		player = card_for.player
		deck = player.cardholders[Pile.DECK]
		hand = player.cardholders[Pile.HAND]

		if(len(deck) == 0):
			return card_for.generate_response(ResponseType.SKIP, {"msg": "no card in discard to draw"})
		bottom_card = list(deck)[-1]

		if(isinstance(bottom_card, AVGEBirb)):
			target = card_for.env.cache.get(card_for, RaffleTicket._HEAL_TARGET_KEY, None, one_look=True)
			if(target is None):
				def _input_valid(result) -> bool:
					return (
						len(result) == 1
						and (result[0] in card_for.player.get_cards_in_play())
					)

				return card_for.generate_response(
					ResponseType.INTERRUPT,
					{
						INTERRUPT_KEY: [
							InputEvent(
								player,
								[RaffleTicket._HEAL_TARGET_KEY],
								InputType.DETERMINISTIC,
								_input_valid,
								ActionTypes.NONCHAR,
								card_for,
								{
									"query_label": "raffle_ticket_birb",
									"targets": card_for.player.get_cards_in_play()
								},
							)
						]
					},
				)

			card_for.propose(
				AVGECardHPChange(
					target,
					target.maxhp,
					AVGEAttributeModifier.SET_STATE,
					target.card_type,
					ActionTypes.NONCHAR,
					card_for,
				)
			)

		card_for.propose(
			TransferCard(
				bottom_card,
				deck,
				hand,
				ActionTypes.NONCHAR,
				card_for,
			)
		)
		return card_for.generate_response()
