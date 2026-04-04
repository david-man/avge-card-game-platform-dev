from __future__ import annotations

import random

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class CastReserve(AVGEItemCard):
	_PLAYER_ITEM_SELECTION_KEY = "castreserve_player_item_selection"
	_OPPONENT_SHUFFLE_SELECTION_KEY = "castreserve_opponent_shuffle_selection"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card_for: AVGECharacterCard, parent_event: AVGEEvent, args: Data = None) -> Response:
		from card_game.internal_events import InputEvent, TransferCard, ReorderCardholder
		player = card_for.player
		opponent = player.opponent
		deck = player.cardholders[Pile.DECK]
		hand = player.cardholders[Pile.HAND]

		deck_items = [c for c in deck if isinstance(c, AVGEItemCard)]
		unique_item_types = {type(c) for c in deck_items}
		if(len(unique_item_types) < 3):
			return card_for.generate_response()

		def _player_pick_valid(result) -> bool:
			if(len(result) != 3):
				return False
			for c in result:
				if(not isinstance(c, AVGEItemCard) or c not in deck):
					return False
			return len({type(c) for c in result}) == 3

		

		player_keys = [CastReserve._PLAYER_ITEM_SELECTION_KEY + str(i) for i in range(3)]
		opp_keys = [CastReserve._OPPONENT_SHUFFLE_SELECTION_KEY + str(i) for i in range(2)]
		def _opponent_shuffle_pick_valid(result) -> bool:
			if len(result) != 2:
				return False
			selected_three = [card_for.env.cache.get(card_for, key, None) for key in player_keys]
			if selected_three[0] is None:
				return False
			for c in result:
				if(c not in selected_three):
					return False
			return True
		selected_three = [card_for.env.cache.get(card_for, key, None) for key in player_keys]
		if(selected_three[0] is None):
			return card_for.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							player,
							player_keys,
							InputType.DETERMINISTIC,
							_player_pick_valid,
							ActionTypes.NONCHAR,
							card_for,
							{
								"query_label": "cast_reserve_player_item_pick",
								"deck-items": deck_items,
							},
						)
					]
				},
			)

		chosen_for_shuffle = [card_for.env.cache.get(card_for, key, None) for key in opp_keys]
		if(chosen_for_shuffle[0] is None):
			return card_for.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							opponent,
							opp_keys,
							InputType.DETERMINISTIC,
							_opponent_shuffle_pick_valid,
							ActionTypes.NONCHAR,
							card_for,
							{
								"query_label": "cast_reserve_opponent_shuffle_choice",
								"targets": selected_three
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
			return card_for.generate_response(ResponseType.SKIP, {"msg": "CastReserve selection resolution failed."})

		packet = [TransferCard(
				card_to_hand,
				deck,
				hand,
				ActionTypes.NONCHAR,
				card_for,
			),
			TransferCard(
				chosen_for_shuffle[0],
				deck,
				deck,
				ActionTypes.NONCHAR,
				card_for,
				lambda : random.randint(0, len(deck))
			),
			TransferCard(
				chosen_for_shuffle[1],
				deck,
				deck,
				ActionTypes.NONCHAR,
				card_for,
				lambda : random.randint(0, len(deck))
			),
			]

		card_for.propose(packet)
		return card_for.generate_response()
