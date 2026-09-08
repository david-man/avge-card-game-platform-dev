from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import InputEvent, TransferCard


class VideoCamera(AVGEItemCard):
	_DISCARD_ITEM_PICK_KEY = 'videocamera_discard_item_pick'

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self, card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:
		player = card.player
		discard = player.cardholders[Pile.DISCARD]
		deck = player.cardholders[Pile.DECK]

		discard_items = [c for c in discard if isinstance(c, AVGEItemCard)]
		missing = object()
		chosen = card.env.cache.get(card, VideoCamera._DISCARD_ITEM_PICK_KEY, missing, one_look=True)
		if(chosen is missing):
			return Response(
				ResponseType.INTERRUPT,
				Interrupt[AVGEEvent]([
						InputEvent(
							player,
							[VideoCamera._DISCARD_ITEM_PICK_KEY],
							lambda res : True,
							ActionTypes.NONCHAR,
							card,
							CardSelectionQuery('Video Camera: Choose an item in your discard to move to the top of your deck (or None).', discard_items, list(discard), True, False)
						)
					]),
			)

		if chosen is None:
			return self.generic_response(card)

		if not isinstance(chosen, AVGEItemCard) or chosen not in discard_items:
			raise Exception('VideoCamera: Invalid discard item selection')

		card.propose(
			AVGEPacket([
				TransferCard(
					chosen,
					discard,
					deck,
					ActionTypes.NONCHAR,
					card,
					None,
					0,
				)
			], AVGEEngineID(card, ActionTypes.NONCHAR, VideoCamera))
		)

		return self.generic_response(card)
