from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class Lucas(AVGESupporterCard):
	_CARD_DECK_KEY = "lucas_selected_top_deck"
	_CARD_HAND_KEY = "lucas_selected_hand"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self, card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:
		from card_game.internal_events import InputEvent, TransferCard
		player = card.player
		deck = player.cardholders[Pile.DECK]
		hand = player.cardholders[Pile.HAND]

		board_characters: list[AVGECharacterCard] = []
		for character in player.get_cards_in_play():
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

		missing = object()
		top_deck_card = card.env.cache.get(card, Lucas._CARD_DECK_KEY, missing)
		hand_card = card.env.cache.get(card, Lucas._CARD_HAND_KEY, missing, True)
		if(top_deck_card is missing):
			return Response(
				ResponseType.INTERRUPT,
				Interrupt[InputEvent]([
					InputEvent(
						card.player,
						[Lucas._CARD_DECK_KEY],
						lambda res: True,
						ActionTypes.NONCHAR,
						card,
						CardSelectionQuery("lucas_choice_top", eligible_deck_characters, eligible_deck_characters, True, False),
					)
				]),
			)
		if(top_deck_card is not None):
			assert isinstance(top_deck_card, AVGECharacterCard)
			eligible_deck_characters = [
				card
				for card in eligible_deck_characters
				if card != top_deck_card and card.card_type != top_deck_card.card_type
			]
		if(hand_card is missing):
			return Response(
				ResponseType.INTERRUPT,
				Interrupt[InputEvent]([
					InputEvent(
						card.player,
						[Lucas._CARD_HAND_KEY],
						lambda res: True,
						ActionTypes.NONCHAR,
						card,
						CardSelectionQuery("lucas_choice_hand", eligible_deck_characters, eligible_deck_characters, True, False),
					)
				]),
			)

		packet: PacketType = []
		if top_deck_card is not None:
			assert isinstance(top_deck_card, AVGECharacterCard)
			packet.append(
				TransferCard(
					top_deck_card,
					deck,
					deck,
					ActionTypes.NONCHAR,
					card,
					RevealCards("Lucas: Selected top-deck character", all_players, default_timeout, [top_deck_card]),
					0,
				)
			)
		if hand_card is not None:
			assert isinstance(hand_card, AVGECharacterCard)
			packet.append(
				TransferCard(
					hand_card,
					deck,
					hand,
					ActionTypes.NONCHAR,
					card,
					RevealCards("Lucas: Selected hand character", all_players, default_timeout, [hand_card]),
				)
			)

		if(len(packet) > 0):
			card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, Lucas)))
		card.env.cache.delete(card, Lucas._CARD_DECK_KEY)
		card.env.cache.delete(card, Lucas._CARD_HAND_KEY)
		return self.generic_response(card)
