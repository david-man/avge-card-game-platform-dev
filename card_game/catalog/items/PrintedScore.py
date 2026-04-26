from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import EmptyEvent, InputEvent, TransferCard


class PrintedScore(AVGEItemCard):
	_OPPONENT_HAND_DISCARD_KEY = 'printedscore_opponent_hand_discard'

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self, card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:
		env = card.env
		if(env.round_id == 0):
			return Response(ResponseType.SKIP, Notify('Cannot play PrintedScore on the first turn.', [card.player.unique_id], default_timeout))

		opponent = card.player.opponent
		opponent_hand = opponent.cardholders[Pile.HAND]
		opponent_discard = opponent.cardholders[Pile.DISCARD]

		if(len(opponent_hand) == 0):
			return Response(ResponseType.SKIP, Notify('PrintedScore: Opponent has no cards in hand.', [card.player.unique_id], default_timeout))
		
		
		missing = object()
		chosen = env.cache.get(card, PrintedScore._OPPONENT_HAND_DISCARD_KEY, missing, one_look=True)
		if(chosen is missing):
			return Response(
				ResponseType.INTERRUPT,
				Interrupt[AVGEEvent]([
						InputEvent(
							opponent,
							[PrintedScore._OPPONENT_HAND_DISCARD_KEY],
							lambda res : True,
							ActionTypes.NONCHAR,
							card,
							CardSelectionQuery('Printed Score: Opponent chooses one revealed hand card to discard.', list(opponent_hand), list(opponent_hand), False, False)
						)
					]),
			)
		if not isinstance(chosen, AVGECard) or chosen not in opponent_hand:
			raise Exception('PrintedScore: invalid opponent hand selection')
		card.propose(
			AVGEPacket([
				EmptyEvent(
					ActionTypes.NONCHAR,
					card,
					ResponseType.CORE,
					RevealCards('Printed Score: Opponent hand', all_players, default_timeout, list(opponent_hand)),
				),

				TransferCard(
					chosen,
					opponent_hand,
					opponent_discard,
					ActionTypes.NONCHAR,
					card,
					None,
				)
			], AVGEEngineID(card, ActionTypes.NONCHAR, PrintedScore))
		)

		return self.generic_response(card)
