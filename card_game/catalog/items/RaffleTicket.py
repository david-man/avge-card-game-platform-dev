from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class RaffleTicket(AVGEItemCard):
	_HEAL_TARGET_KEY = "raffleticket_heal_target"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card) -> Response:
		from card_game.catalog.items.AVGEBirb import AVGEBirb
		from card_game.internal_events import AVGECardHPChange, InputEvent, TransferCard
		player = card.player
		deck = player.cardholders[Pile.DECK]
		hand = player.cardholders[Pile.HAND]

		if(len(deck) == 0):
			return card.generate_response(ResponseType.SKIP, {"msg": "no card in discard to draw"})
		bottom_card = list(deck)[-1]

		if(isinstance(bottom_card, AVGEBirb)):
			target = card.env.cache.get(card, RaffleTicket._HEAL_TARGET_KEY, None, one_look=True)
			if(target is None):
				def _input_valid(result) -> bool:
					return (
						len(result) == 1
						and (result[0] in card.player.get_cards_in_play())
					)

				return card.generate_response(
					ResponseType.INTERRUPT,
					{
						INTERRUPT_KEY: [
							InputEvent(
								player,
								[RaffleTicket._HEAL_TARGET_KEY],
								InputType.DETERMINISTIC,
								_input_valid,
								ActionTypes.NONCHAR,
								card,
								{
									"query_label": "raffle_ticket_birb",
									"targets": card.player.get_cards_in_play()
								},
							)
						]
					},
				)

			card.propose(
				AVGEPacket([
					AVGECardHPChange(
						target,
						target.maxhp,
						AVGEAttributeModifier.SET_STATE,
						target.card_type,
						ActionTypes.NONCHAR,
						card,
					)
				], AVGEEngineID(card, ActionTypes.NONCHAR, RaffleTicket))
			)

		card.propose(
			AVGEPacket([
				TransferCard(
					bottom_card,
					deck,
					hand,
					ActionTypes.NONCHAR,
					card,
				)
			], AVGEEngineID(card, ActionTypes.NONCHAR, RaffleTicket))
		)
		return card.generate_response()
