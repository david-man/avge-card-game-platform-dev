from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class Lucas(AVGESupporterCard):
	_CARD_DECK_KEY = "lucas_selected_top_deck"
	_CARD_HAND_KEY = "lucas_selected_hand"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	@staticmethod
	def play_card(card: AVGECard) -> Response:
		from card_game.internal_events import InputEvent, TransferCard
		player = card.player
		deck = player.cardholders[Pile.DECK]
		hand = player.cardholders[Pile.HAND]

		board_characters: list[AVGECharacterCard] = []
		for target_player in [player, player.opponent]:
			for character in target_player.cardholders[Pile.ACTIVE]:
				if(isinstance(character, AVGECharacterCard)):
					board_characters.append(character)
			for character in target_player.cardholders[Pile.BENCH]:
				if(isinstance(character, AVGECharacterCard)):
					board_characters.append(character)

		board_types = {
			character.card_type
			for character in board_characters
		}

		eligible_deck_characters = [
			card
			for card in deck
			if isinstance(card, AVGECharacterCard)
			and card.card_type not in board_types
		]

		if(len(eligible_deck_characters) < 1):
			return card.generate_response(ResponseType.CORE)


		def _input_valid(result) -> bool:
			if(len(result) != 2):
				return False
			top_deck = result[0]
			hand_pick = result[1]
			if(top_deck is not None and top_deck not in eligible_deck_characters):
				return False
			if(hand_pick is not None and hand_pick not in eligible_deck_characters):
				return False
			if(top_deck is not None and hand_pick is not None and top_deck == hand_pick):
				return False
			return True

		missing = object()
		top_deck_card = card.env.cache.get(card, Lucas._CARD_DECK_KEY, missing, True)
		hand_card = card.env.cache.get(card, Lucas._CARD_HAND_KEY, missing, True)
		if(top_deck_card is missing):
			return card.generate_interrupt([
				InputEvent(
					card.player,
					[Lucas._CARD_DECK_KEY, Lucas._CARD_HAND_KEY],
					InputType.DETERMINISTIC,
					_input_valid,
					ActionTypes.NONCHAR,
					card,
					{"query_label": "lucas-choice",
	  				"targets": eligible_deck_characters}
				)
			])

		packet = []
		if top_deck_card is not None:
			packet.append(TransferCard(top_deck_card,
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
			card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, Lucas)))
		return card.generate_response(ResponseType.CORE)
