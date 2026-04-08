from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

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
			return card.generate_response(ResponseType.SKIP, {MESSAGE_KEY: "Opponent has no cards in discard."})

		if(len(opponent_hand) == 0):
			return card.generate_response(ResponseType.SKIP, {MESSAGE_KEY: "Opponent has no cards in hand to reveal."})

		hand_pick = card.env.cache.get(card, AnnotatedScore._OPPONENT_HAND_DISCARD_KEY, None)
		
		if(hand_pick is None):
			return card.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							card.player,
							[AnnotatedScore._OPPONENT_HAND_DISCARD_KEY],
							InputType.SELECTION,
							lambda r : True,
							ActionTypes.NONCHAR,
							card,
							{
								"query_label": "annotated_score_hand",
								"targets": list(opponent_hand),
								"display": list(opponent_hand)
							},
						)
					]
				},
			)
		discard_pick = card.env.cache.get(card, AnnotatedScore._OPPONENT_DISCARD_RETURN_KEY, None, True)
		if(hand_pick is None):
			return card.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							card.player,
							[AnnotatedScore._OPPONENT_DISCARD_RETURN_KEY],
							InputType.SELECTION,
							lambda r : True,
							ActionTypes.NONCHAR,
							card,
							{
								"query_label": "annotated_score_discard",
								"targets": list(opponent_discard)
							},
						)
					]
				},
			)
		assert discard_pick is not None
		packet : PacketType= [
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
		card.env.cache.delete(card, AnnotatedScore._OPPONENT_HAND_DISCARD_KEY)
		return card.generate_response()
