from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

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
		if(len(deck) == 0):
			return card.generate_response(ResponseType.FAST_FORWARD, {MESSAGE_KEY: "No cards in deck!"})
		missing = object()
		top_deck_card = card.env.cache.get(card, Lucas._CARD_DECK_KEY, missing)
		hand_card = card.env.cache.get(card, Lucas._CARD_HAND_KEY, missing, True)
		if(top_deck_card is missing):
			return card.generate_response(ResponseType.INTERRUPT,
								 {
									 INTERRUPT_KEY:[
										 InputEvent(
											card.player,
											[Lucas._CARD_DECK_KEY],
											InputType.SELECTION,
											lambda res : True,
											ActionTypes.NONCHAR,
											card,
											{"query_label": "lucas_choice_top",
											"targets": eligible_deck_characters,
											"display": deck}
										)
									]
								 }
				)
		if(top_deck_card is not None):
			assert isinstance(top_deck_card, AVGECard)
			eligible_deck_characters = [
				card
				for card in eligible_deck_characters
				if not isinstance(card, type(top_deck_card))
			]
		if(hand_card is missing):
			return card.generate_response(ResponseType.INTERRUPT,
								 {
									 INTERRUPT_KEY:[
										 InputEvent(
											card.player,
											[Lucas._CARD_HAND_KEY],
											InputType.SELECTION,
											lambda res : True,
											ActionTypes.NONCHAR,
											card,
											{"query_label": "lucas_choice_hand",
											"targets": eligible_deck_characters,
											"display": deck}
										)
									]
								 }
				)

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
