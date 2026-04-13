from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class IceSkates(AVGEItemCard):
	_BENCH_TARGET_KEY = "iceskates_bench_target"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card) -> Response:
		from card_game.internal_events import InputEvent, TransferCard
		player = card.player
		active = player.get_active_card()

		bench = player.cardholders[Pile.BENCH]
		active_holder = player.cardholders[Pile.ACTIVE]
		bench_targets = [c for c in bench if isinstance(c, AVGECharacterCard)]

		if(len(bench_targets) == 0):
			return card.generate_response(ResponseType.SKIP, {MESSAGE_KEY: "No benched characters to switch with."})

		bench_target = card.env.cache.get(card, IceSkates._BENCH_TARGET_KEY, None, one_look=True)
		if(bench_target is None):
			return card.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							player,
							[IceSkates._BENCH_TARGET_KEY],
							InputType.SELECTION,
							lambda re : True,
							ActionTypes.NONCHAR,
							card,
							{
								LABEL_FLAG: "iceskates_switch_bench",
								TARGETS_FLAG: bench_targets,
								DISPLAY_FLAG: bench_targets
							},
						)
					]
				},
			)

		card.propose(
			AVGEPacket([
				TransferCard(
					bench_target,
					bench,
					active_holder,
					ActionTypes.NONCHAR,
					card,
				),
				TransferCard(
					active,
					active_holder,
					bench,
					ActionTypes.NONCHAR,
					card,
				),
			], AVGEEngineID(card, ActionTypes.NONCHAR, IceSkates))
		)

		return card.generate_response()
