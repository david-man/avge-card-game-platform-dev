from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class IceSkates(AVGEItemCard):
	_BENCH_TARGET_KEY = "iceskates_bench_target"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card_for: AVGECharacterCard, parent_event: AVGEEvent, args: Data = None) -> Response:
		from card_game.internal_events import InputEvent, TransferCard
		player = card_for.player
		active = player.get_active_card()

		bench = player.cardholders[Pile.BENCH]
		active_holder = player.cardholders[Pile.ACTIVE]
		bench_targets = [c for c in bench if isinstance(c, AVGECharacterCard)]

		if(len(bench_targets) == 0):
			return card_for.generate_response(ResponseType.SKIP, {"msg": "No benched characters to switch with."})

		def _input_valid(result) -> bool:
			return len(result) == 1 and isinstance(result[0], AVGECharacterCard) and result[0] in bench_targets

		bench_target = card_for.env.cache.get(card_for, IceSkates._BENCH_TARGET_KEY, None, one_look=True)
		if(bench_target is None):
			return card_for.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							player,
							[IceSkates._BENCH_TARGET_KEY],
							InputType.DETERMINISTIC,
							_input_valid,
							ActionTypes.NONCHAR,
							card_for,
							{
								"query_label": "iceskates_switch_bench",
								"targets": bench_targets
							},
						)
					]
				},
			)

		card_for.propose(
			[
				TransferCard(
					bench_target,
					bench,
					active_holder,
					ActionTypes.NONCHAR,
					card_for,
				),
				TransferCard(
					active,
					active_holder,
					bench,
					ActionTypes.NONCHAR,
					card_for,
				),
			]
		)

		return card_for.generate_response()
