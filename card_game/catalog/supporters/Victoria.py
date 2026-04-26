from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class Victoria(AVGESupporterCard):
	_SELECTED_TYPE_KEY = "victoria_selected_type"
	_CARD_DECK_KEY = "victoria_selected_top_deck"
	_CARD_HAND_KEY = "victoria_selected_hand"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self, card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:
		from card_game.internal_events import InputEvent, TransferCard

		player = card.player
		deck = player.cardholders[Pile.DECK]
		hand = player.cardholders[Pile.HAND]

		type_options = [str(t) for t in CardType if t != CardType.ALL]

		missing = object()
		selected_type_raw = card.env.cache.get(card, Victoria._SELECTED_TYPE_KEY, missing)
		if(selected_type_raw is missing):
			return Response(
				ResponseType.INTERRUPT,
				Interrupt[InputEvent]([
						InputEvent(
							player,
							[Victoria._SELECTED_TYPE_KEY],
							lambda res: True,
							ActionTypes.NONCHAR,
							card,
							StrSelectionQuery("victoria_pick_type", type_options, type_options, False, False),
						)
				]),
			)

		selected_type = CardType(selected_type_raw)

		matching_characters = [
			candidate
			for candidate in deck
			if isinstance(candidate, AVGECharacterCard)
			and candidate.card_type == selected_type
		]

		deck_card = card.env.cache.get(card, Victoria._CARD_DECK_KEY, missing)
		hand_card = card.env.cache.get(card, Victoria._CARD_HAND_KEY, missing, True)

		if(deck_card is missing):
			return Response(
				ResponseType.INTERRUPT,
				Interrupt[InputEvent]([
					InputEvent(
						player,
						[Victoria._CARD_DECK_KEY],
						lambda res: True,
						ActionTypes.NONCHAR,
						card,
						CardSelectionQuery("victoria_pick_top", matching_characters, matching_characters, True, False),
					)
				]),
			)

		remaining_for_hand = matching_characters
		if(deck_card is not None):
			remaining_for_hand = [candidate for candidate in matching_characters if candidate != deck_card]

		if(hand_card is missing):
			return Response(
				ResponseType.INTERRUPT,
				Interrupt[InputEvent]([
						InputEvent(
							player,
							[Victoria._CARD_HAND_KEY],
							lambda res: True,
							ActionTypes.NONCHAR,
							card,
							CardSelectionQuery("victoria_pick_hand", remaining_for_hand, remaining_for_hand, True, False),
						)
				]),
			)

		packet: PacketType = []
		if deck_card is not None:
			deck_card = cast(AVGECharacterCard, deck_card)
			packet.append(
				TransferCard(
					deck_card,
					deck,
					deck,
					ActionTypes.NONCHAR,
					card,
					RevealCards("Victoria: Selected top-deck character", all_players, default_timeout, [deck_card]),
					0,
				)
			)
		if hand_card is not None:
			hand_card = cast(AVGECharacterCard, hand_card)
			packet.append(
				TransferCard(
					hand_card,
					deck,
					hand,
					ActionTypes.NONCHAR,
					card,
					RevealCards("Victoria: Selected hand character", all_players, default_timeout, [hand_card]),
				)
			)

		if(len(packet) > 0):
			card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, Victoria)))
		card.env.cache.delete(card, Victoria._SELECTED_TYPE_KEY)
		card.env.cache.delete(card, Victoria._CARD_DECK_KEY)
		card.env.cache.delete(card, Victoria._CARD_HAND_KEY)
		return self.generic_response(card)
