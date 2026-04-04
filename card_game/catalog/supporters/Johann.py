from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class Johann(AVGESupporterCard):
	_SUPPORTER_PICK_KEY = "johann_discard_supporter_pick"
	_ITEM_OR_TOOL_PICK_KEY = "johann_discard_item_or_tool_pick"
	_STADIUM_PICK_KEY = "johann_discard_stadium_pick"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	@staticmethod
	def play_card(card_for: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
		from card_game.internal_events import InputEvent, TransferCard, TurnEnd

		player = card_for.player
		discard = player.cardholders[Pile.DISCARD]
		hand = player.cardholders[Pile.HAND]

		supporters_in_discard = [c for c in discard if isinstance(c, AVGESupporterCard)]
		items_or_tools_in_discard = [
			c
			for c in discard
			if isinstance(c, AVGEItemCard) or isinstance(c, AVGEToolCard)
		]
		stadiums_in_discard = [c for c in discard if isinstance(c, AVGEStadiumCard)]

		packet = []
		if(len(supporters_in_discard) > 0 or len(items_or_tools_in_discard) > 0 or len(stadiums_in_discard) > 0):
			
			def _input_valid(result) -> bool:
				if(len(result) != 3):
					return False

				supporter_pick = result[0]
				item_or_tool_pick = result[1]
				stadium_pick = result[2]

				if(supporter_pick is not None and supporter_pick not in supporters_in_discard):
					return False
				if(item_or_tool_pick is not None and item_or_tool_pick not in items_or_tools_in_discard):
					return False
				if(stadium_pick is not None and stadium_pick not in stadiums_in_discard):
					return False

				return True

			missing = object()
			supporter_pick = card_for.env.cache.get(card_for, Johann._SUPPORTER_PICK_KEY, missing, one_look=True)
			item_or_tool_pick = card_for.env.cache.get(card_for, Johann._ITEM_OR_TOOL_PICK_KEY, missing, one_look=True)
			stadium_pick = card_for.env.cache.get(card_for, Johann._STADIUM_PICK_KEY, missing, one_look=True)

			if(supporter_pick is missing):
				return card_for.generate_interrupt([
							InputEvent(
								player,
								[
									Johann._SUPPORTER_PICK_KEY,
									Johann._ITEM_OR_TOOL_PICK_KEY,
									Johann._STADIUM_PICK_KEY,
								],
								InputType.DETERMINISTIC,
								_input_valid,
								ActionTypes.NONCHAR,
								card_for,
								{
									"query_label": "johann_3card_query",
									"supporters": supporters_in_discard,
									"items": items_or_tools_in_discard,
									"stadiums": stadiums_in_discard,
								},
							)
						])

			if(supporter_pick is not None):
				packet.append(
					TransferCard(
						supporter_pick,
						discard,
						hand,
						ActionTypes.NONCHAR,
						card_for,
					)
				)
			if(item_or_tool_pick is not None):
				packet.append(
					TransferCard(
						item_or_tool_pick,
						discard,
						hand,
						ActionTypes.NONCHAR,
						card_for,
					)
				)
			if(stadium_pick is not None):
				packet.append(
					TransferCard(
						stadium_pick,
						discard,
						hand,
						ActionTypes.NONCHAR,
						card_for,
					)
				)

		packet.append(TurnEnd(card_for.env, ActionTypes.NONCHAR, card_for))
		card_for.propose(packet)
		return card_for.generate_response(ResponseType.CORE)
