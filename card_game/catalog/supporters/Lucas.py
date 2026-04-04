from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class Lucas(AVGESupporterCard):
	_CARD_DECK_KEY = "lucas_selected_top_deck"
	_CARD_HAND_KEY = "lucas_selected_hand"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	@staticmethod
	def play_card(card_for: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
		from card_game.internal_events import InputEvent, TransferCard
		player = card_for.player
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
			character.attributes.get(AVGECardAttribute.TYPE)
			for character in board_characters
			if character.attributes.get(AVGECardAttribute.TYPE) is not None
		}

		eligible_deck_characters = [
			card
			for card in deck
			if isinstance(card, AVGECharacterCard)
			and card.attributes.get(AVGECardAttribute.TYPE) not in board_types
		]

		if(len(eligible_deck_characters) < 1):
			return card_for.generate_response(ResponseType.CORE)


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
		top_deck_card = card_for.env.cache.get(card_for, Lucas._CARD_DECK_KEY, missing, True)
		hand_card = card_for.env.cache.get(card_for, Lucas._CARD_HAND_KEY, missing, True)
		if(top_deck_card is missing):
			return card_for.generate_interrupt([
				InputEvent(
					card_for.player,
					[Lucas._CARD_DECK_KEY, Lucas._CARD_HAND_KEY],
					InputType.DETERMINISTIC,
					_input_valid,
					ActionTypes.NONCHAR,
					card_for,
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
							  card_for,
							  0))
		if hand_card is not None:
			packet.append(TransferCard(hand_card,
							  deck,
							  hand,
							  ActionTypes.NONCHAR,
							  card_for))


		if(len(packet) > 0):
			card_for.propose(packet)
		return card_for.generate_response(ResponseType.CORE)
