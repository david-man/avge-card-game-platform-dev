from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class Johann(AVGESupporterCard):
	_SUPPORTER_PICK_KEY = "johann_discard_supporter_pick"
	_ITEM_OR_TOOL_PICK_KEY = "johann_discard_item_or_tool_pick"
	_STADIUM_PICK_KEY = "johann_discard_stadium_pick"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	@staticmethod
	def play_card(card: AVGECard) -> Response:
		from card_game.internal_events import InputEvent, TransferCard, TurnEnd

		player = card.player
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
		missing = object()
		supporter_pick = card.env.cache.get(card, Johann._SUPPORTER_PICK_KEY, missing)
		item_or_tool_pick = card.env.cache.get(card, Johann._ITEM_OR_TOOL_PICK_KEY, missing)
		stadium_pick = card.env.cache.get(card, Johann._STADIUM_PICK_KEY, missing, one_look=True)
		if(supporter_pick is missing):
			return card.generate_response(ResponseType.INTERRUPT,
					{INTERRUPT_KEY:[
						[
					InputEvent(
						player,
						[Johann._SUPPORTER_PICK_KEY],
						InputType.SELECTION,
						lambda res : True,
						ActionTypes.NONCHAR,
						card,
						{
							"query_label": "johann_3card_query_supporter",
							"target": supporters_in_discard,
							"display": list(discard),
							"allow_none": True,
						},
					)
						]
					]})
		if(item_or_tool_pick is missing):
			return card.generate_response(ResponseType.INTERRUPT,
					{INTERRUPT_KEY:[
						[
					InputEvent(
						player,
						[Johann._ITEM_OR_TOOL_PICK_KEY],
						InputType.SELECTION,
						lambda res : True,
						ActionTypes.NONCHAR,
						card,
						{
							"query_label": "johann_3card_query_item",
							"target": items_or_tools_in_discard,
							"display": list(discard),
							"allow_none": True,
						},
					)
						]
					]})
		
		if(stadium_pick is missing):
			return card.generate_response(ResponseType.INTERRUPT,
					{INTERRUPT_KEY:[
						[
					InputEvent(
						player,
						[Johann._STADIUM_PICK_KEY],
						InputType.SELECTION,
						lambda res : True,
						ActionTypes.NONCHAR,
						card,
						{
							"query_label": "johann_3card_query_stadium",
							"target": stadiums_in_discard,
							"display": list(discard),
							"allow_none": True,
						},
					)
						]
					]})

		if(supporter_pick is not None):
			packet.append(
				TransferCard(
					supporter_pick,
					discard,
					hand,
					ActionTypes.NONCHAR,
					card,
				)
			)
		if(item_or_tool_pick is not None):
			packet.append(
				TransferCard(
					item_or_tool_pick,
					discard,
					hand,
					ActionTypes.NONCHAR,
					card,
				)
			)
		if(stadium_pick is not None):
			packet.append(
				TransferCard(
					stadium_pick,
					discard,
					hand,
					ActionTypes.NONCHAR,
					card,
				)
			)

		packet.append(TurnEnd(card.env, ActionTypes.NONCHAR, card))
		card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, Johann)))
		card.env.cache.delete(card, Johann._ITEM_OR_TOOL_PICK_KEY)
		card.env.cache.delete(card, Johann._SUPPORTER_PICK_KEY)
		return card.generate_response(ResponseType.CORE)
