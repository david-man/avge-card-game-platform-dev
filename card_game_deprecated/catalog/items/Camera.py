from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import InputEvent, TransferCard

class Camera(AVGEItemCard):
	_DISCARD_PICK_KEY = 'camera_discard_supporter_or_stadium_pick'

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self, card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:
		player = card.player
		target_discard = player.cardholders[Pile.DISCARD]
		deck = player.cardholders[Pile.DECK]

		eligible_cards = [
			c
			for c in target_discard
			if isinstance(c, AVGESupporterCard) or isinstance(c, AVGEStadiumCard)
		]

		missing = object()
		chosen = card.env.cache.get(card, Camera._DISCARD_PICK_KEY, missing, one_look=True)
		if(chosen is missing):
			return Response(
				ResponseType.INTERRUPT,
				Interrupt[AVGEEvent]([
						InputEvent(
							player,
							[Camera._DISCARD_PICK_KEY],
							lambda res : True,
							ActionTypes.NONCHAR,
							card,
							CardSelectionQuery('Camera: Choose a Supporter or Stadium to shuffle into your deck.', eligible_cards, list(target_discard), True, False)
						)
					]),
			)

		if chosen is None:
			return self.generic_response(card)

		def gen() -> PacketType:
			return [TransferCard(
					chosen,
					target_discard,
					deck,
					ActionTypes.NONCHAR,
					card,
					None,
					random.randint(0, len(deck)),
				)]
		card.propose(
			AVGEPacket([
				gen
			], AVGEEngineID(card, ActionTypes.NONCHAR, Camera))
		)

		return self.generic_response(card)
