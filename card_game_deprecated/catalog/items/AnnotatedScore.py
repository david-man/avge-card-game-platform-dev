from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import EmptyEvent, InputEvent, TransferCard


class AnnotatedScore(AVGEItemCard):
	_OPPONENT_HAND_DISCARD_KEY = 'annotatedscore_opponent_hand_discard'
	_OPPONENT_DISCARD_RETURN_KEY = 'annotatedscore_opponent_discard_return'

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self, card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:
		opponent = card.player.opponent
		opponent_hand = opponent.cardholders[Pile.HAND]
		opponent_discard = opponent.cardholders[Pile.DISCARD]

		if len(opponent_discard) == 0 or len(opponent_hand) == 0:
			return Response(
				ResponseType.FAST_FORWARD,
				Notify('Conditions for using AnnotatedScore were not met...', [card.player.unique_id], default_timeout)
			)

		missing = object()
		hand_pick_probe = card.env.cache.get(card, AnnotatedScore._OPPONENT_HAND_DISCARD_KEY, missing, False)
		if hand_pick_probe is missing:
			return Response(
				ResponseType.INTERRUPT,
				Interrupt[AVGEEvent]([
						InputEvent(
							card.player,
							[AnnotatedScore._OPPONENT_HAND_DISCARD_KEY],
							lambda r: True,
							ActionTypes.NONCHAR,
							card,
							CardSelectionQuery(
								'Annotated Score: Choose one revealed opponent hand card to discard.',
								list(opponent_hand),
								list(opponent_hand),
								False,
								False,
							),
						),
					]),
			)
		discard_pick_probe = card.env.cache.get(card, AnnotatedScore._OPPONENT_DISCARD_RETURN_KEY, missing, False)
		if discard_pick_probe is missing:
			return Response(
				ResponseType.INTERRUPT,
				Interrupt[AVGEEvent]([
						InputEvent(
							card.player,
							[AnnotatedScore._OPPONENT_DISCARD_RETURN_KEY],
							lambda r: True,
							ActionTypes.NONCHAR,
							card,
							CardSelectionQuery(
								'Annotated Score: Choose a different opponent discard card to return to hand.',
								list(opponent_discard),
								list(opponent_discard),
								False,
								False,
							),
						),
					]),
			)

		hand_pick = card.env.cache.get(card, AnnotatedScore._OPPONENT_HAND_DISCARD_KEY, None, True)
		discard_pick = card.env.cache.get(card, AnnotatedScore._OPPONENT_DISCARD_RETURN_KEY, None, True)
		if (
			not isinstance(hand_pick, AVGECard)
			or hand_pick not in opponent_hand
			or not isinstance(discard_pick, AVGECard)
			or discard_pick not in opponent_discard
			or discard_pick == hand_pick
		):
			raise Exception("Something went wrong in Annotated Score")

		packet: PacketType = [
			TransferCard(
				hand_pick,
				opponent_hand,
				opponent_discard,
				ActionTypes.NONCHAR,
				card,
				None,
			),
			TransferCard(
				discard_pick,
				opponent_discard,
				opponent_hand,
				ActionTypes.NONCHAR,
				card,
				None,
			),
		]
		card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, AnnotatedScore)))
		return self.generic_response(card)
