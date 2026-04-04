from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class BAIEmailStadiumPlayLockAssessor(AVGEAssessor):
	def __init__(self, owner_card: AVGEItemCard):
		super().__init__(identifier=(owner_card, AVGEEventListenerType.NONCHAR), group=EngineGroup.EXTERNAL_PRECHECK_1)
		self.owner_card = owner_card

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
		round_until = int(self.owner_card.env.cache.get(self.owner_card, BAIEmail._STADIUM_LOCK_UNTIL_KEY, 0))
		if(self.owner_card.env.round_id > round_until):
			self.invalidate()

	def make_announcement(self) -> bool:
		return True

	def package(self):
		return "BAIEmail Stadium Lock Assessor"

	def assess(self, args={}):
		return self.generate_response(ResponseType.SKIP, {"msg": "BAIEmail: stadium cards cannot be played right now."})


class BAIEmail(AVGEItemCard):
	_STADIUM_PICK_KEY = "baiemail_stadium_pick"
	_STADIUM_LOCK_UNTIL_KEY = "baiemail_stadium_lock_until"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card_for: AVGECharacterCard, parent_event: AVGEEvent, args: Data = None) -> Response:
		from card_game.internal_events import InputEvent, TransferCard, PlayNonCharacterCard, TurnEnd

		card_for.env.cache.set(card_for, BAIEmail._STADIUM_LOCK_UNTIL_KEY, card_for.player.get_next_turn())
		lock_assessor = BAIEmailStadiumPlayLockAssessor(card_for)
		card_for.add_listener(lock_assessor)

		packet = []
		if(len(card_for.env.stadium_cardholder) > 0):
			active_stadium : AVGEStadiumCard  = card_for.env.stadium_cardholder.peek()
			discard_owner = active_stadium.original_owner 
			packet.append(TransferCard(
							active_stadium,
							card_for.env.stadium_cardholder,
							discard_owner.cardholders[Pile.DISCARD],
							ActionTypes.NONCHAR,
							card_for,
						))

		deck = card_for.player.cardholders[Pile.DECK]
		hand = card_for.player.cardholders[Pile.HAND]
		stadiums_in_deck = [c for c in deck if isinstance(c, AVGEStadiumCard)]

		if(len(stadiums_in_deck) > 0):
			def _input_valid(result) -> bool:
				return len(result) == 1 and isinstance(result[0], AVGEStadiumCard) and result[0] in stadiums_in_deck

			picked_stadium = card_for.env.cache.get(card_for, BAIEmail._STADIUM_PICK_KEY, None, one_look=True)
			if(picked_stadium is None):
				return card_for.generate_response(
					ResponseType.INTERRUPT,
					{
						INTERRUPT_KEY: [
							InputEvent(
								card_for.player,
								[BAIEmail._STADIUM_PICK_KEY],
								InputType.DETERMINISTIC,
								_input_valid,
								ActionTypes.NONCHAR,
								card_for,
								{
									"query_label": "baiemail_stadium_pick",
									"stadiums": stadiums_in_deck,
								},
							)
						]
					},
				)

			packet.append(
				TransferCard(
					picked_stadium,
					deck,
					hand,
					ActionTypes.NONCHAR,
					card_for,
				)
			)
		if(len(packet) > 0):
			card_for.propose(packet)

		return card_for.generate_response()
