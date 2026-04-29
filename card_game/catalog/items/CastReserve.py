from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import EmptyEvent, InputEvent, TransferCard

class CastReserve(AVGEItemCard):
	_PLAYER_ITEM_SELECTION_KEY = 'castreserve_player_item_selection_'
	_OPPONENT_SHUFFLE_SELECTION_KEY = 'castreserve_opponent_shuffle_selection_'

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self, card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:
		player = card.player
		opponent = player.opponent
		deck = player.cardholders[Pile.DECK]
		hand = player.cardholders[Pile.HAND]

		deck_items = [c for c in deck if isinstance(c, AVGEItemCard)]

		player_keys = [CastReserve._PLAYER_ITEM_SELECTION_KEY + str(i) for i in range(3)]
		opp_keys = [CastReserve._OPPONENT_SHUFFLE_SELECTION_KEY + str(i) for i in range(2)]
		missing = object()
		selected_probe = [card.env.cache.get(card, key, missing, False) for key in player_keys]

		def _check_player_choice(result):
			if len(result) != 3:
				return False
			if(all(s is None for s in result)):
				return True
			if not all(isinstance(s, AVGEItemCard) for s in result):
				return False
			if not all(s in deck for s in result):
				return False
			return len({type(s) for s in result}) == 3

		if selected_probe[0] is missing:
			return Response(
				ResponseType.INTERRUPT,
				Interrupt[AVGEEvent]([
						InputEvent(
							player,
							player_keys,
							_check_player_choice,
							ActionTypes.NONCHAR,
							card,
							CardSelectionQuery('Cast Reserve: Either choose 3 unique item cards from your deck or choose none at all.', deck_items, list(deck), True, False)
						)
					]),
			)

		selected_three_raw = [card.env.cache.get(card, key, None, False) for key in player_keys]
		selected_three: list[AVGEItemCard] = []
		for c in selected_three_raw:
			if(c is None):
				return self.generic_response(card)
			assert isinstance(c, AVGEItemCard)
			selected_three.append(c)

		chosen_for_shuffle_probe = [card.env.cache.get(card, key, missing, False) for key in opp_keys]
		if chosen_for_shuffle_probe[0] is missing:
			return Response(
				ResponseType.INTERRUPT,
				Interrupt[AVGEEvent]([
						InputEvent(
							opponent,
							opp_keys,
							lambda b : True,
							ActionTypes.NONCHAR,
							card,
							CardSelectionQuery('CastReserve: Choose 2 of the chosen items to shuffle back.', selected_three, selected_three, False, False)
						)
					]),
			)

		selected_three = [card.env.cache.get(card, key, None, True) for key in player_keys]#type: ignore
		chosen_for_shuffle = [card.env.cache.get(card, key, None, True) for key in opp_keys]

		card_to_hand = None
		for c in selected_three:
			if(c not in chosen_for_shuffle):
				card_to_hand = c
				break
		if card_to_hand is None or not isinstance(card_to_hand, AVGEItemCard):
			raise Exception('CastReserve: Could not resolve card to hand')

		def gen_1() -> PacketType:
			assert isinstance(chosen_for_shuffle[0], AVGECard)
			return [TransferCard(
				chosen_for_shuffle[0],
				deck,
				deck,
				ActionTypes.NONCHAR,
				card,
				None,
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
				None,
				random.randint(0, len(deck))
			)]
		packet: PacketType = [
			TransferCard(
				card_to_hand,
				deck,
				hand,
				ActionTypes.NONCHAR,
				card,
				None,
			),
			gen_1,
			gen_2,
		]

		card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, CastReserve)))
		return self.generic_response(card)
