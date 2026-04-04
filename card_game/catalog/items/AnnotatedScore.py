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
	def play_card(card_for: AVGECharacterCard, parent_event: AVGEEvent, args: Data = None) -> Response:
		from card_game.internal_events import InputEvent, TransferCard

		opponent = card_for.player.opponent

		opponent_hand = opponent.cardholders[Pile.HAND]
		opponent_discard = opponent.cardholders[Pile.DISCARD]

		if(len(opponent_discard) == 0):
			return card_for.generate_response(ResponseType.SKIP, {"msg": "Opponent has no cards in discard."})

		if(len(opponent_hand) == 0):
			return card_for.generate_response(ResponseType.SKIP, {"msg": "Opponent has no cards in hand to reveal."})

		hand_pick = card_for.env.cache.get(card_for, AnnotatedScore._OPPONENT_HAND_DISCARD_KEY, None, True)
		discard_pick = card_for.env.cache.get(card_for, AnnotatedScore._OPPONENT_DISCARD_RETURN_KEY, None, True)
		if(hand_pick is None):
			def _valid(result):
				if(len(result) != 2):
					return False
				return result[0] in opponent_hand and result[1] in opponent_discard
			return card_for.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							card_for.player,
							[AnnotatedScore._OPPONENT_HAND_DISCARD_KEY, AnnotatedScore._OPPONENT_DISCARD_RETURN_KEY],
							InputType.DETERMINISTIC,
							_valid,
							ActionTypes.NONCHAR,
							card_for,
							{
								"query_label": "annotated_score_discard_hand",
								"opponent_hand": list(opponent_hand),
								"opponent_discard": list(opponent_discard)
							},
						)
					]
				},
			)
		packet = [
			TransferCard(
				discard_pick,
				opponent_discard,
				opponent_hand,
				ActionTypes.NONCHAR,
				card_for,
			),
			TransferCard(
				hand_pick,
				opponent_hand,
				opponent_discard,
				ActionTypes.NONCHAR,
				card_for,
			)
		]
		card_for.propose(packet)
		return card_for.generate_response()
