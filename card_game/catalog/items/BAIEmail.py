from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class BAIEmailStadiumPlayLockAssessor(AVGEAssessor):
	def __init__(self, owner_card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard, round_until : int =0):
		super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.NONCHAR, BAIEmail), group=EngineGroup.EXTERNAL_PRECHECK_1)
		self.owner_card = owner_card
		self.round_until = round_until

	def event_match(self, event):
		from card_game.internal_events import PlayNonCharacterCard
		if(not isinstance(event, PlayNonCharacterCard)):
			return False
		if(not isinstance(event.card, AVGEStadiumCard)):
			return False
		return event.catalyst_action == ActionTypes.PLAYER_CHOICE

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
		return self.generate_response(ResponseType.SKIP, {MESSAGE_KEY: "BAIEmail: stadium cards cannot be played right now."})


class BAIEmail(AVGEItemCard):
	_STADIUM_PICK_KEY = "baiemail_stadium_pick"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card) -> Response:
		from card_game.internal_events import InputEvent, TransferCard

		lock_assessor = BAIEmailStadiumPlayLockAssessor(card, card.player.get_next_turn())
		card.add_listener(lock_assessor)

		packet : PacketType = []
		if(len(card.env.stadium_cardholder) > 0):
			x = card.env.stadium_cardholder.peek()
			assert isinstance(x, AVGEStadiumCard)
			active_stadium : AVGEStadiumCard = x
			discard_owner = active_stadium.original_owner 
			assert discard_owner is not None
			packet.append(TransferCard(
							active_stadium,
							card.env.stadium_cardholder,
							discard_owner.cardholders[Pile.DISCARD],
							ActionTypes.NONCHAR,
							card,
						))

		deck = card.player.cardholders[Pile.DECK]
		hand = card.player.cardholders[Pile.HAND]
		stadiums_in_deck = [c for c in deck if isinstance(c, AVGEStadiumCard)]
		missing = object()
		picked_stadium = card.env.cache.get(card, BAIEmail._STADIUM_PICK_KEY, missing, one_look=True)
		if(picked_stadium is missing):
			return card.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							card.player,
							[BAIEmail._STADIUM_PICK_KEY],
							InputType.SELECTION,
							lambda res : True,
							ActionTypes.NONCHAR,
							card,
							{
								"query_label": "baiemail_stadium_pick",
								"targets": stadiums_in_deck,
								"display": list(deck),
								"allow_none": True
							},
						)
					]
				},
			)
		if picked_stadium is not None:
			packet.append(
				TransferCard(
					picked_stadium,
					deck,
					hand,
					ActionTypes.NONCHAR,
					card,
				)
			)
		if(len(packet) > 0):
			card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, BAIEmail)))

		return card.generate_response()
