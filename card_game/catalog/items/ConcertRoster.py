from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import EmptyEvent, InputEvent, TransferCard


class ConcertRoster(AVGEItemCard):
	_TOP_PICK_KEY = 'concertroster_top_pick'

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self, card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:
		deck = card.player.cardholders[Pile.DECK]
		hand = card.player.cardholders[Pile.HAND]

		consider_count = min(3, len(deck))
		considered_cards = list(deck.peek_n(consider_count))
		pick_choices = [c for c in considered_cards if isinstance(c, AVGECharacterCard) or isinstance(c, AVGEStadiumCard)]
		missing = object()
		picked_card = card.env.cache.get(card, ConcertRoster._TOP_PICK_KEY, missing, one_look=True)
		if(picked_card is missing):
			return Response(
				ResponseType.INTERRUPT,
				Interrupt[AVGEEvent]([
						InputEvent(
							card.player,
							[ConcertRoster._TOP_PICK_KEY],
							lambda r: True,
							ActionTypes.NONCHAR,
							card,
							CardSelectionQuery('Concert Roster: Choose a character or stadium from the top 3.', pick_choices, considered_cards, True, False)
						)
					]),
			)
		packet : PacketType = []
		if isinstance(picked_card, (AVGECharacterCard, AVGEStadiumCard)) and picked_card in considered_cards:
			packet.append(
				EmptyEvent(
					ActionTypes.NONCHAR,
					card,
					ResponseType.CORE,
					RevealCards('Concert Roster: Revealed card', all_players, default_timeout, [picked_card]),
				)
			)
			packet.append(
				TransferCard(
					picked_card,
					deck,
					hand,
					ActionTypes.NONCHAR,
					card,
					None,
				)
			)
		if len(packet) > 0:
			card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, ConcertRoster)))
		return self.generic_response(card)
