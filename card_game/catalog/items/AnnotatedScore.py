from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class AnnotatedScore(AVGEItemCard):
	_OPPONENT_HAND_DISCARD_KEY = "annotatedscore_opponent_hand_discard"
	_OPPONENT_DISCARD_RETURN_KEY = "annotatedscore_opponent_discard_return"
	_HAND_TRANSFER_DONE_KEY = "annotatedscore_hand_transfer_done"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card) -> Response:
		from card_game.internal_events import InputEvent, TransferCard

		opponent = card.player.opponent

		opponent_hand = opponent.cardholders[Pile.HAND]
		opponent_discard = opponent.cardholders[Pile.DISCARD]

		if(len(opponent_discard) == 0):
			return card.generate_response(ResponseType.SKIP, {"msg": "Opponent has no cards in discard."})

		if(len(opponent_hand) == 0):
			return card.generate_response(ResponseType.SKIP, {"msg": "Opponent has no cards in hand to reveal."})

		hand_pick = card.env.cache.get(card, AnnotatedScore._OPPONENT_HAND_DISCARD_KEY, None, True)
		discard_pick = card.env.cache.get(card, AnnotatedScore._OPPONENT_DISCARD_RETURN_KEY, None, True)
		if(hand_pick is None):
			def _valid(result):
				if(len(result) != 2):
					return False
				return result[0] in opponent_hand and result[1] in opponent_discard
			return card.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							card.player,
							[AnnotatedScore._OPPONENT_HAND_DISCARD_KEY, AnnotatedScore._OPPONENT_DISCARD_RETURN_KEY],
							InputType.DETERMINISTIC,
							_valid,
							ActionTypes.NONCHAR,
							card,
							{
								"query_label": "annotated_score_discard_hand",
								"opponent_hand": list(opponent_hand),
								"opponent_discard": list(opponent_discard)
							},
						)
					]
				},
			)
		assert discard_pick is not None
		packet = [
			TransferCard(
				discard_pick,
				opponent_discard,
				opponent_hand,
				ActionTypes.NONCHAR,
				card,
			),
			TransferCard(
				hand_pick,
				opponent_hand,
				opponent_discard,
				ActionTypes.NONCHAR,
				card,
			)
		]
		card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, AnnotatedScore)))
		return card.generate_response()
