from __future__ import annotations

import random

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class DressRehearsalRoster(AVGEItemCard):
	_ENERGY_REMOVAL_SELECTION_KEY_1 = "dressrehearsalroster_energy_removal_selection_1"
	_ENERGY_REMOVAL_SELECTION_KEY_2 = "dressrehearsalroster_energy_removal_selection_2"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card_for: AVGECharacterCard, parent_event: AVGEEvent, args: Data = None) -> Response:
		from card_game.internal_events import InputEvent, TransferCard, AVGEEnergyTransfer
		player = card_for.player
		deck = player.cardholders[Pile.DECK]
		discard = player.cardholders[Pile.DISCARD]

		in_play_characters = player.get_cards_in_play()

		total_energy = sum(len(c.energy) for c in in_play_characters)
		if(total_energy < 2):
			return card_for.generate_response(ResponseType.SKIP, {"msg": "Not enough total energy in play for DressRehearsalRoster."})
		
		selected_chars = [card_for.env.cache.get(card_for, DressRehearsalRoster._ENERGY_REMOVAL_SELECTION_KEY_1, None, one_look=True), card_for.env.cache.get(card_for, DressRehearsalRoster._ENERGY_REMOVAL_SELECTION_KEY_2, None, one_look=True)]
		if(selected_chars[0] is None):
			def _input_valid(result):
				if len(result) != 2:
					return False
				if not isinstance(result[0], AVGECharacterCard) or not isinstance(result[1], AVGECharacterCard):
					return False
				if result[0] not in in_play_characters or result[1] not in in_play_characters:
					return False
				if(result[0] == result[1]):
					return len(result[0].energy) >= 2
				else:
					return len(result[0].energy) >= 1 and len(result[1].energy) >= 1
			return card_for.generate_response(
				ResponseType.INTERRUPT,
				{
					INTERRUPT_KEY: [
						InputEvent(
							player,
							[DressRehearsalRoster._ENERGY_REMOVAL_SELECTION_KEY_1, DressRehearsalRoster._ENERGY_REMOVAL_SELECTION_KEY_2],
							InputType.DETERMINISTIC,
							_input_valid,
							ActionTypes.NONCHAR,
							card_for,
							{
								"query_label": "dress_rehearsal_roster_energy_remove",
								"targets": in_play_characters
							},
						)
					]
				},
			)
		def generate_packet():
			packet = []
			for selected in selected_chars:
				packet.append(
					AVGEEnergyTransfer(
						selected.energy[0],
						selected,
						selected.player,
						ActionTypes.NONCHAR,
						card_for,
					)
				)

			cards_to_shuffle = list(discard)
			if(len(cards_to_shuffle) > 4):
				cards_to_shuffle = random.sample(cards_to_shuffle, 4)

			for card_to_shuffle in cards_to_shuffle:
				packet.append(
					TransferCard(
						card_to_shuffle,
						discard,
						deck,
						ActionTypes.NONCHAR,
						card_for,
						lambda: random.randint(0, len(deck)),
					)
				)
			return packet

		card_for.propose(generate_packet)
		return card_for.generate_response()
