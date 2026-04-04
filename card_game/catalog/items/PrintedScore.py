from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class PrintedScore(AVGEItemCard):
	_OPPONENT_HAND_DISCARD_KEY = "printedscore_opponent_hand_discard"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card_for: AVGECharacterCard, parent_event: AVGEEvent, args: Data = None) -> Response:
		from card_game.internal_events import InputEvent, TransferCard
		env = card_for.env
		if(env.round_id == 0):
			return card_for.generate_response(ResponseType.SKIP, {"msg": "Cannot play PrintedScore on the first turn."})

		opponent = card_for.player.opponent
		opponent_hand = opponent.cardholders[Pile.HAND]
		opponent_discard = opponent.cardholders[Pile.DISCARD]

		if(len(opponent_hand) == 0):
			return card_for.generate_response(ResponseType.SKIP, {"msg": "opponent has no cards in hand"})

		def _input_valid(result) -> bool:
			if(len(result) != 1):
				return False
			chosen = result[0]
			return isinstance(chosen, Card) and chosen in opponent_hand

		missing = object()
		chosen = env.cache.get(card_for, PrintedScore._OPPONENT_HAND_DISCARD_KEY, missing, one_look=True)
		if(chosen is missing):
			return card_for.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							opponent,
							[PrintedScore._OPPONENT_HAND_DISCARD_KEY],
							InputType.DETERMINISTIC,
							_input_valid,
							ActionTypes.NONCHAR,
							card_for,
							{
								"query_label": "printed_score_discard",
								"targets": opponent_hand
							},
						)
					]
				},
			)

		card_for.propose(
			TransferCard(
				chosen,
				opponent_hand,
				opponent_discard,
				ActionTypes.NONCHAR,
				card_for,
			)
		)

		return card_for.generate_response()
