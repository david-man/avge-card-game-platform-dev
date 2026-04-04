from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class AVGEShowcaseStickerTurnStartReactor(AVGEReactor):
	def __init__(self, owner_card: AVGEToolCard):
		super().__init__(
			identifier=(owner_card, AVGEEventListenerType.PASSIVE),
			group=EngineGroup.EXTERNAL_REACTORS,
		)
		self.owner_card = owner_card

	def event_match(self, event):
		from card_game.internal_events import PhasePickCard

		if(not isinstance(event, PhasePickCard)):
			return False
		return (
			event.player == self.owner_card.card_attached.player
			and self.owner_card.card_attached.player.get_active_card() == self.owner_card.card_attached
		)

	def event_effect(self) -> bool:
		return True

	def update_status(self):
		if(self.owner_card.cardholder is None or self.owner_card.cardholder.pile_type == Pile.DISCARD):
			self.invalidate()

	def make_announcement(self) -> bool:
		return True

	def package(self):
		return "AVGEAmbassador Reactor"

	def react(self, args={}):
		from card_game.internal_events import InputEvent, TransferCard
		player = self.owner_card.player
		coin_val = self.owner_card.env.cache.get(self.owner_card, AVGEShowcaseSticker._COIN_RESULT_KEY, None, one_look=True)
		if(coin_val is None):

			return self.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							player,
							[AVGEShowcaseSticker._COIN_RESULT_KEY],
							InputType.COIN,
							lambda r: True,
							ActionTypes.NONCHAR,
							self.owner_card,
							{
								"querying_card": "sticker-coin-flip"},
						)
					]
				},
			)

		if(int(coin_val) == 1):
			deck = player.cardholders[Pile.DECK]
			hand = player.cardholders[Pile.HAND]
			if(len(deck) > 0):
				self.propose(
					TransferCard(
						deck.peek(),
						deck,
						hand,
						ActionTypes.NONCHAR,
						self.owner_card,
					)
				)

		return self.generate_response()


class AVGEShowcaseSticker(AVGEToolCard):
	_COIN_RESULT_KEY = "avgeshowcasesticker_coin_result"
	_ATTACHED_CHARACTER_KEY = "avgeshowcasesticker_attached_character"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self, parent_event: AVGEEvent) -> Response:
		self.add_listener(AVGEShowcaseStickerTurnStartReactor(self))
		return self.generate_response()
