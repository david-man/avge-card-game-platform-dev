from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import InputEvent, TransferCard

class IceSkates(AVGEItemCard):
	_BENCH_TARGET_KEY = 'iceskates_bench_target'

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self, card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:
		player = card.player
		active = player.get_active_card()

		bench = player.cardholders[Pile.BENCH]
		active_holder = player.cardholders[Pile.ACTIVE]
		bench_targets = [c for c in bench if isinstance(c, AVGECharacterCard)]

		if(len(bench_targets) == 0):
			return Response(
				ResponseType.CORE,
				Notify('Ice Skates was used, but there are no benched characters to switch with...', [player.unique_id], default_timeout)
			)

		missing = object()
		bench_target = card.env.cache.get(card, IceSkates._BENCH_TARGET_KEY, missing, one_look=True)
		if(bench_target is missing):
			return Response(
				ResponseType.INTERRUPT,
				Interrupt[AVGEEvent]([
						InputEvent(
							player,
							[IceSkates._BENCH_TARGET_KEY],
							lambda re : True,
							ActionTypes.NONCHAR,
							card,
							CardSelectionQuery('Ice Skates: Choose one benched character to switch with your active.', bench_targets, bench_targets, False, False)
						)
					]),
			)

		if not isinstance(bench_target, AVGECharacterCard) or bench_target not in bench_targets:
			raise Exception('IceSkates: invalid bench selection')
		if not isinstance(active, AVGECharacterCard):
			raise Exception('IceSkates: active card is invalid')

		card.propose(
			AVGEPacket([
				TransferCard(
					bench_target,
					bench,
					active_holder,
					ActionTypes.NONCHAR,
					card,
					None,
				),
				TransferCard(
					active,
					active_holder,
					bench,
					ActionTypes.NONCHAR,
					card,
					None,
				),
			], AVGEEngineID(card, ActionTypes.NONCHAR, IceSkates))
		)

		return self.generic_response(card)
