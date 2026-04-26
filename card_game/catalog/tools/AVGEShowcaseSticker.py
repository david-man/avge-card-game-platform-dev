from __future__ import annotations

from card_game.avge_abstracts import *

from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class AVGEShowcaseStickerTurnStartReactor(AVGEReactor):
	def __init__(self, owner_card: AVGEToolCard):
		super().__init__(
			identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, AVGEShowcaseSticker),
			group=EngineGroup.EXTERNAL_REACTORS,
		)
		self.owner_card = owner_card

	def event_match(self, event):
		from card_game.internal_events import PhasePickCard

		if(not isinstance(event, PhasePickCard)):
			return False
		if(self.owner_card.card_attached is None or self.owner_card.card_attached.player is None):
			return False
		return (
			event.env.player_turn == self.owner_card.card_attached.player
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

	def react(self, args=None):
		from card_game.internal_events import InputEvent, TransferCard
		player = self.owner_card.player
		coin_val = self.owner_card.env.cache.get(self.owner_card, AVGEShowcaseSticker._COIN_RESULT_KEY, None)
		if(coin_val is None):
			return Response(
				ResponseType.INTERRUPT,
				Interrupt[InputEvent]([
						InputEvent(
							player,
							[AVGEShowcaseSticker._COIN_RESULT_KEY],
							lambda r: True,
							ActionTypes.PASSIVE,
							self.owner_card,
							CoinflipData("AVGE Ambassador: Flip a coin."),
						)
				]),
			)

		if(int(coin_val) == 1):
			deck = player.cardholders[Pile.DECK]
			hand = player.cardholders[Pile.HAND]
			if(len(deck) > 0):
				def gen() -> PacketType:
					return [TransferCard(
							deck.peek(),
							deck,
							hand,
							ActionTypes.PASSIVE,
							self.owner_card,
							None,
						)]
				self.propose(
					AVGEPacket([
						gen
					], AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, AVGEShowcaseSticker)), 1
				)

		self.owner_card.env.cache.delete(self.owner_card, AVGEShowcaseSticker._COIN_RESULT_KEY)
		return Response(ResponseType.ACCEPT, Data())


class AVGEShowcaseSticker(AVGEToolCard):
	_COIN_RESULT_KEY = "avgeshowcasesticker_coin_result"
	_ATTACHED_CHARACTER_KEY = "avgeshowcasesticker_attached_character"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self) -> Response:
		self.add_listener(AVGEShowcaseStickerTurnStartReactor(self))
		return Response(ResponseType.CORE, Data())
