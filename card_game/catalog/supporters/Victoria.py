from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class Victoria(AVGESupporterCard):
	_SELECTED_TYPE_KEY = "victoria_selected_type"
	_SELECTED_CARDS_KEY = "victoria_selected_cards"
	_CARD_DECK_KEY = "victoria_selected_top_deck"
	_CARD_HAND_KEY = "victoria_selected_hand"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	@staticmethod
	def play_card(card: AVGECard) -> Response:
		from card_game.internal_events import InputEvent, TransferCard

		player = card.player
		deck = player.cardholders[Pile.DECK]
		hand = player.cardholders[Pile.HAND]

		def _type_input_valid(result) -> bool:
			if(len(result) != 1):
				return False
			picked = result[0]
			return isinstance(picked, CardType)

		selected_type = card.env.cache.get(card, Victoria._SELECTED_TYPE_KEY, None)
		if(selected_type is None):
			return card.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							player,
							[Victoria._SELECTED_TYPE_KEY],
							InputType.DETERMINISTIC,
							_type_input_valid,
							ActionTypes.NONCHAR,
							card,
							{
								"query_label": "victoria_pick_type"
							},
						)
					]
				},
			)
		matching_characters = [
			card
			for card in deck
			if isinstance(card, AVGECharacterCard)
			and card.card_type == selected_type
		]

		if(len(matching_characters) < 1):
			card.env.cache.delete(card, Victoria._SELECTED_TYPE_KEY)
			return card.generate_response(ResponseType.CORE)

		def _cards_and_destination_input_valid(result) -> bool:
			if(len(result) != 2 or not isinstance(result[0], list)):
				return False
			top_deck = result[0]
			hand = result[1]
			if(top_deck not in matching_characters and top_deck is not None):
				return False
			if(hand not in matching_characters and hand is not None):
				return False
			if(top_deck == hand):
				return False
			return True

		missing = object()
		deck_card = card.env.cache.get(card, Victoria._CARD_DECK_KEY, missing, one_look=True)
		hand_card = card.env.cache.get(card, Victoria._CARD_HAND_KEY, missing, one_look=True)

		if(hand_card is missing):
			return card.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							player,
							[Victoria._CARD_DECK_KEY, Victoria._CARD_HAND_KEY],
							InputType.DETERMINISTIC,
							_cards_and_destination_input_valid,
							ActionTypes.NONCHAR,
							card,
							{
								"query_label": "victoria_pick_cards_and_destination",
								"targets": matching_characters
							},
						)
					]
				},
			)

		card.env.cache.delete(card, Victoria._SELECTED_TYPE_KEY)

		packet = []
		if deck_card is not None:
			packet.append(TransferCard(deck_card,
							  deck,
							  deck,
							  ActionTypes.NONCHAR,
							  card,
							  0))
		if hand_card is not None:
			packet.append(TransferCard(hand_card,
							  deck,
							  hand,
							  ActionTypes.NONCHAR,
							  card))

		if(len(packet) > 0):
			card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, Victoria)))
		return card.generate_response(ResponseType.CORE)
