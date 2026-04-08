from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *

from card_game.constants import ActionTypes
class VideoCamera(AVGEItemCard):
	_DISCARD_ITEM_PICK_KEY = "videocamera_discard_item_pick"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	@staticmethod
	def play_card(card) -> Response:
		from card_game.internal_events import InputEvent, TransferCard

		player = card.player
		discard = player.cardholders[Pile.DISCARD]
		deck = player.cardholders[Pile.DECK]

		discard_items = [c for c in discard if isinstance(c, AVGEItemCard)]
		missing = object()
		chosen = card.env.cache.get(card, VideoCamera._DISCARD_ITEM_PICK_KEY, missing, one_look=True)
		if(chosen is missing):
			return card.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							player,
							[VideoCamera._DISCARD_ITEM_PICK_KEY],
							InputType.DETERMINISTIC,
							lambda res : True,
							ActionTypes.NONCHAR,
							card,
							{
								"query_label": "video_camera_discard_item_pick",
								"targets": discard_items,
								"display": list(discard),
								"allow_none": True
							},
						)
					]
				},
			)
		if(chosen is not None):
			card.propose(
				AVGEPacket([
					TransferCard(
						chosen,
						discard,
						deck,
						ActionTypes.NONCHAR,
						card,
						0,
					)
				], AVGEEngineID(card, ActionTypes.NONCHAR, VideoCamera))
			)

		return card.generate_response()
