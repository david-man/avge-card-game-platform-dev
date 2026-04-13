from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class CastReserve(AVGEItemCard):
	_PLAYER_ITEM_SELECTION_KEY = "castreserve_player_item_selection"
	_OPPONENT_SHUFFLE_SELECTION_KEY = "castreserve_opponent_shuffle_selection"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card) -> Response:
		from card_game.internal_events import InputEvent, TransferCard, ReorderCardholder
		player = card.player
		opponent = player.opponent
		deck = player.cardholders[Pile.DECK]
		hand = player.cardholders[Pile.HAND]

		deck_items = [c for c in deck if isinstance(c, AVGEItemCard)]
		player_keys = [CastReserve._PLAYER_ITEM_SELECTION_KEY + str(i) for i in range(3)]
		opp_keys = [CastReserve._OPPONENT_SHUFFLE_SELECTION_KEY + str(i) for i in range(2)]
		selected_three = [card.env.cache.get(card, key, None) for key in player_keys]

		def _check_player_choice(result):
			if(len(result) != 3):
				return False
			return result[0] is None or len({type(s) for s in result}) == 3
		if(selected_three[0] is None):
			return card.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							player,
							player_keys,
							InputType.DETERMINISTIC,
							_check_player_choice,
							ActionTypes.NONCHAR,
							card,
							{
								LABEL_FLAG: "cast_reserve_player_item_pick",
								TARGETS_FLAG: deck_items,
								DISPLAY_FLAG: deck_items,
								ALLOW_NONE: True,
								ALLOW_REPEAT: False
							},
						)
					]
				},
			)

		chosen_for_shuffle = [card.env.cache.get(card, key, None) for key in opp_keys]
		if(chosen_for_shuffle[0] is None):
			return card.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							opponent,
							opp_keys,
							InputType.SELECTION,
							lambda b : True,
							ActionTypes.NONCHAR,
							card,
							{
								LABEL_FLAG: "cast_reserve_opponent_shuffle_choice",
								TARGETS_FLAG: selected_three,
								DISPLAY_FLAG: selected_three
							},
						)
					]
				},
			)

		card_to_hand = None
		for c in selected_three:
			if(c not in chosen_for_shuffle):
				card_to_hand = c
				break
		if(card_to_hand is None or chosen_for_shuffle[1] is None):
			return card.generate_response(ResponseType.SKIP, {MESSAGE_KEY: "CastReserve selection resolution failed."})
		def gen_1() -> PacketType:
			assert isinstance(chosen_for_shuffle[0], AVGECard)
			return [TransferCard(
				chosen_for_shuffle[0],
				deck,
				deck,
				ActionTypes.NONCHAR,
				card,
				random.randint(0, len(deck))
			)]
		def gen_2() -> PacketType:
			assert isinstance(chosen_for_shuffle[1], AVGECard)
			return [TransferCard(
				chosen_for_shuffle[1],
				deck,
				deck,
				ActionTypes.NONCHAR,
				card,
				random.randint(0, len(deck))
			)]
		packet = [TransferCard(
				card_to_hand,
				deck,
				hand,
				ActionTypes.NONCHAR,
				card,
			),gen_1, gen_2
			]

		card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, CastReserve)))
		return card.generate_response()
