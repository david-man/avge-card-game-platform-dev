from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import EmptyEvent, InputEvent, ReorderCardholder, TransferCard


class ConcertProgram(AVGEItemCard):
	_TOP_CHARACTER_PICK_KEY = 'concertprogram_top_character_pick'

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self, card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:
		deck = card.player.cardholders[Pile.DECK]
		hand = card.player.cardholders[Pile.HAND]

		consider_count = min(5, len(deck))
		considered_cards = list(deck.peek_n(consider_count))
		character_choices = [c for c in considered_cards if isinstance(c, AVGECharacterCard)]

		missing = object()
		picked_character = card.env.cache.get(card, ConcertProgram._TOP_CHARACTER_PICK_KEY, missing, one_look=True)
		if(picked_character is missing):
			return Response(
				ResponseType.INTERRUPT,
				Interrupt[AVGEEvent]([
						InputEvent(
							card.player,
							[ConcertProgram._TOP_CHARACTER_PICK_KEY],
							lambda r : True,
							ActionTypes.NONCHAR,
							card,
							CardSelectionQuery('Concert Program: Choose a character from the top 5 to reveal and put into your hand.', character_choices, considered_cards, True, False)
						)
					]),
			)
		packet : PacketType = []
		
		if(isinstance(picked_character, AVGECharacterCard) and picked_character in considered_cards):
			packet.append(
				EmptyEvent(
					ActionTypes.NONCHAR,
					card,
					ResponseType.CORE,
					RevealCards('Concert Program: Revealed character', all_players, default_timeout, [picked_character]),
				)
			)
			packet.append(
				TransferCard(
					picked_character,
					deck,
					hand,
					ActionTypes.NONCHAR,
					card,
					None,
				)
			)
		def gen() -> PacketType:
			return[
				ReorderCardholder(
					deck,
					[c.unique_id for c in random.sample(list(deck), len(deck))],
					ActionTypes.NONCHAR,
					card,
					None,
				)
			]
		packet.append(gen)

		card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, ConcertProgram)))
		return self.generic_response(card)
