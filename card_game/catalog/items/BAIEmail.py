from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import InputEvent, PlayNonCharacterCard, TransferCard


class BAIEmailStadiumPlayLockAssessor(AVGEAssessor):
	def __init__(self, owner_card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard, round_until: int):
		super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.NONCHAR, BAIEmail), group=EngineGroup.EXTERNAL_PRECHECK_1)
		self.owner_card = owner_card
		self.round_until = round_until

	def event_match(self, event):
		if(not isinstance(event, PlayNonCharacterCard)):
			return False
		if(not isinstance(event.card, AVGEStadiumCard)):
			return False
		return True

	def event_effect(self) -> bool:
		return True

	def update_status(self):
		if(self.owner_card.env.round_id > self.round_until):
			self.invalidate()

	def make_announcement(self) -> bool:
		return True

	def package(self):
		return "BAIEmail Stadium Lock Assessor"

	def assess(self, args=None):
		return Response(ResponseType.SKIP, Notify('BAIEmail: Stadium cards cannot be played right now.', all_players, default_timeout))


class BAIEmail(AVGEItemCard):
	_STADIUM_PICK_KEY = 'baiemail_stadium_pick'

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self, card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:
		packet : PacketType = []
		if(len(card.env.stadium_cardholder) > 0):
			x = card.env.stadium_cardholder.peek()
			assert isinstance(x, AVGEStadiumCard)
			active_stadium : AVGEStadiumCard = x
			discard_owner = active_stadium.player 
			assert discard_owner is not None
			packet.append(TransferCard(
							active_stadium,
							card.env.stadium_cardholder,
							discard_owner.cardholders[Pile.DISCARD],
							ActionTypes.NONCHAR,
							card,
							None,
						))

		deck = card.player.cardholders[Pile.DECK]
		hand = card.player.cardholders[Pile.HAND]
		stadiums_in_deck = [c for c in deck if isinstance(c, AVGEStadiumCard)]
		missing = object()
		picked_stadium = card.env.cache.get(card, BAIEmail._STADIUM_PICK_KEY, missing, one_look=True)
		if(picked_stadium is missing):
			return Response(
				ResponseType.INTERRUPT,
				Interrupt[AVGEEvent]([
						InputEvent(
							card.player,
							[BAIEmail._STADIUM_PICK_KEY],
							lambda res : True,
							ActionTypes.NONCHAR,
							card,
							CardSelectionQuery('BAIEmail: Choose a Stadium from your deck to put into your hand.', stadiums_in_deck, list(deck), True, False)
						)
					]),
			)

		if isinstance(picked_stadium, AVGEStadiumCard):
			packet.append(
				TransferCard(
					picked_stadium,
					deck,
					hand,
					ActionTypes.NONCHAR,
					card,
					None,
				)
			)

		lock_assessor = BAIEmailStadiumPlayLockAssessor(card, card.player.get_next_turn())
		card.add_listener(lock_assessor)
		if(len(packet) > 0):
			card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, BAIEmail)))

		return self.generic_response(card)
