from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes
class PrintedScore(AVGEItemCard):
	_OPPONENT_HAND_DISCARD_KEY = "printedscore_opponent_hand_discard"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card) -> Response:
		from card_game.internal_events import InputEvent, TransferCard, EmptyEvent
		env = card.env
		if(env.round_id == 0):
			return card.generate_response(ResponseType.SKIP, {MESSAGE_KEY: "Cannot play PrintedScore on the first turn."})

		opponent = card.player.opponent
		opponent_hand = opponent.cardholders[Pile.HAND]
		opponent_discard = opponent.cardholders[Pile.DISCARD]

		if(len(opponent_hand) == 0):
			return card.generate_response(ResponseType.SKIP, {MESSAGE_KEY: "opponent has no cards in hand"})
		
		
		chosen = env.cache.get(card, PrintedScore._OPPONENT_HAND_DISCARD_KEY, None, one_look=True)
		if(chosen is None):
			return card.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							opponent,
							[PrintedScore._OPPONENT_HAND_DISCARD_KEY],
							InputType.SELECTION,
							lambda res : True,
							ActionTypes.NONCHAR,
							card,
							{
								"query_label": "printed_score_discard",
								"targets": opponent_hand,
								"display": opponent_hand,
							},
						)
					]
				},
			)
		assert(isinstance(chosen, AVGECard))
		card.propose(
			AVGEPacket([
				EmptyEvent(
					ActionTypes.NONCHAR,
					card,
					response_data={
						REVEAL_KEY: list(opponent_hand)
					}
				),

				TransferCard(
					chosen,
					opponent_hand,
					opponent_discard,
					ActionTypes.NONCHAR,
					card,
				)
			], AVGEEngineID(card, ActionTypes.NONCHAR, PrintedScore))
		)

		return card.generate_response()
