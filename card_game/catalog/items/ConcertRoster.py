from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes
class ConcertRoster(AVGEItemCard):
	_TOP_PICK_KEY = "concertroster_top_pick"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card) -> Response:
		from card_game.internal_events import InputEvent, TransferCard, EmptyEvent


		deck = card.player.cardholders[Pile.DECK]
		hand = card.player.cardholders[Pile.HAND]

		if(len(deck) == 0):
			return card.generate_response(ResponseType.SKIP, {MESSAGE_KEY: "No cards in deck for ConcertRoster."})

		consider_count = min(3, len(deck))
		considered_cards = list(deck.peek_n(consider_count))
		pick_choices = [c for c in considered_cards if isinstance(c, AVGECharacterCard) or isinstance(c, AVGEStadiumCard)]
		missing = object()
		picked_card = card.env.cache.get(card, ConcertRoster._TOP_PICK_KEY, missing)
		if(picked_card is missing):
			return card.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							card.player,
							[ConcertRoster._TOP_PICK_KEY],
							InputType.SELECTION,
							lambda r: True,
							ActionTypes.NONCHAR,
							card,
							{
								LABEL_FLAG: "concert_roster_top_pick",
								DISPLAY_FLAG: considered_cards,
								TARGETS_FLAG: pick_choices,
								ALLOW_NONE: True
							},
						)
					]
				},
			)
		packet : PacketType = []
		if(picked_card is not None):
			packet.append(EmptyEvent(
					ActionTypes.NONCHAR,
					card,
					response_data={
						REVEAL_KEY: list([picked_card])
					}
				))
			packet.append(
				TransferCard(
					picked_card,
					deck,
					hand,
					ActionTypes.NONCHAR,
					card,
				)
			)
		card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, ConcertRoster)))
		return card.generate_response()
