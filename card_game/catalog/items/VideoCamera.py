from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class VideoCamera(AVGEItemCard):
	_DISCARD_ITEM_PICK_KEY = "videocamera_discard_item_pick"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card_for: AVGECharacterCard, parent_event: AVGEEvent, args: Data = None) -> Response:
		from card_game.internal_events import InputEvent, TransferCard

		player = card_for.player
		discard = player.cardholders[Pile.DISCARD]
		deck = player.cardholders[Pile.DECK]

		discard_items = [c for c in discard if isinstance(c, AVGEItemCard)]
		if(len(discard_items) == 0):
			return card_for.generate_response(ResponseType.FAST_FORWARD, {"msg": "no items in discard pile"})

		def _input_valid(result) -> bool:
			if(len(result) != 1):
				return False
			chosen = result[0]
			return isinstance(chosen, AVGEItemCard) and chosen in discard_items

		chosen = card_for.env.cache.get(card_for, VideoCamera._DISCARD_ITEM_PICK_KEY, None, one_look=True)
		if(chosen is None):
			return card_for.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							player,
							[VideoCamera._DISCARD_ITEM_PICK_KEY],
							InputType.DETERMINISTIC,
							_input_valid,
							ActionTypes.NONCHAR,
							card_for,
							{
								"query_label": "video_camera_discard_item_pick",
								"targets": discard_items
							},
						)
					]
				},
			)

		card_for.propose(
			TransferCard(
				chosen,
				discard,
				deck,
				ActionTypes.NONCHAR,
				card_for,
				0,
			)
		)

		return card_for.generate_response()
