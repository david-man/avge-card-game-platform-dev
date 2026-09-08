from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class Johann(AVGESupporterCard):
	_PICK_1_KEY = "johann_discard_pick_1"
	_PICK_2_KEY = "johann_discard_pick_2"
	_PICK_3_KEY = "johann_discard_pick_3"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	@staticmethod
	def _is_valid_pick_set(input_result: list[object]) -> bool:
		if(len(input_result) != 3):
			return False

		supporter_count = 0
		item_or_tool_count = 0
		stadium_count = 0
		seen: list[AVGECard] = []

		for selected in input_result:
			if(selected is None):
				continue
			if(not isinstance(selected, AVGECard)):
				return False
			if(selected in seen):
				return False
			seen.append(selected)

			if(isinstance(selected, AVGESupporterCard)):
				supporter_count += 1
			elif(isinstance(selected, AVGEItemCard) or isinstance(selected, AVGEToolCard)):
				item_or_tool_count += 1
			elif(isinstance(selected, AVGEStadiumCard)):
				stadium_count += 1
			else:
				return False

			if(supporter_count > 1 or item_or_tool_count > 1 or stadium_count > 1):
				return False

		return True

	def play_card(self, card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:
		from card_game.internal_events import InputEvent, TransferCard, TurnEnd

		player = card.player
		discard = player.cardholders[Pile.DISCARD]
		hand = player.cardholders[Pile.HAND]

		eligible_targets = [
			c
			for c in discard
			if isinstance(c, AVGESupporterCard)
			or isinstance(c, AVGEItemCard)
			or isinstance(c, AVGEToolCard)
			or isinstance(c, AVGEStadiumCard)
		]

		missing = object()
		pick_1 = card.env.cache.get(card, Johann._PICK_1_KEY, missing)
		pick_2 = card.env.cache.get(card, Johann._PICK_2_KEY, missing)
		pick_3 = card.env.cache.get(card, Johann._PICK_3_KEY, missing, True)
		if(pick_1 is missing or pick_2 is missing or pick_3 is missing):
			return Response(
				ResponseType.INTERRUPT,
				Interrupt[InputEvent]([
					InputEvent(
						player,
						[Johann._PICK_1_KEY, Johann._PICK_2_KEY, Johann._PICK_3_KEY],
						Johann._is_valid_pick_set,
						ActionTypes.NONCHAR,
						card,
						CardSelectionQuery("johann_3card_query", eligible_targets, list(discard), True, False),
					)
				]),
			)

		packet: PacketType = []
		for selected in [pick_1, pick_2, pick_3]:
			if(selected is None):
				continue
			assert isinstance(selected, AVGECard)
			packet.append(
				TransferCard(
					selected,
					discard,
					hand,
					ActionTypes.NONCHAR,
					card,
					None,
				)
			)

		packet.append(TurnEnd(card.env, ActionTypes.NONCHAR, card))
		card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, Johann)))
		return self.generic_response(card)
