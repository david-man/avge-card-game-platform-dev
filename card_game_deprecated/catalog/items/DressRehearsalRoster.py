from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import AVGEEnergyTransfer, InputEvent, TransferCard

class DressRehearsalRoster(AVGEItemCard):
	_ENERGY_REMOVAL_SELECTION_KEY_1 = 'dressrehearsalroster_energy_removal_selection_1'
	_ENERGY_REMOVAL_SELECTION_KEY_2 = 'dressrehearsalroster_energy_removal_selection_2'

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self, card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:
		player = card.player
		deck = player.cardholders[Pile.DECK]
		discard = player.cardholders[Pile.DISCARD]

		in_play_characters = [c for c in player.get_cards_in_play() if isinstance(c, AVGECharacterCard)]

		total_energy = sum(len(c.energy) for c in in_play_characters)
		if(total_energy < 2):
			return Response(
				ResponseType.FAST_FORWARD,
				Notify('Not enough total energy in play for DressRehearsalRoster...', [player.unique_id], default_timeout)
			)
		
		missing = object()
		selected_probe = [
			card.env.cache.get(card, DressRehearsalRoster._ENERGY_REMOVAL_SELECTION_KEY_1, missing, False),
			card.env.cache.get(card, DressRehearsalRoster._ENERGY_REMOVAL_SELECTION_KEY_2, missing, False)
		]
		if(selected_probe[0] is missing):
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
			return Response(
				ResponseType.INTERRUPT,
				Interrupt[AVGEEvent]([
						InputEvent(
							player,
							[DressRehearsalRoster._ENERGY_REMOVAL_SELECTION_KEY_1, DressRehearsalRoster._ENERGY_REMOVAL_SELECTION_KEY_2],
							_input_valid,
							ActionTypes.NONCHAR,
							card,
							CardSelectionQuery('Dress Rehearsal Roster: Choose 2 (not necessarily distinct) characters to discard energy from.', in_play_characters, in_play_characters, False, True)
						)
					]),
			)

		selected_chars = [
			card.env.cache.get(card, DressRehearsalRoster._ENERGY_REMOVAL_SELECTION_KEY_1, None, True),
			card.env.cache.get(card, DressRehearsalRoster._ENERGY_REMOVAL_SELECTION_KEY_2, None, True)
		]
		if not all(isinstance(sel, AVGECharacterCard) and sel in in_play_characters for sel in selected_chars):
			raise Exception('DressRehearsalRoster: invalid selected characters')

		packet : PacketType = []
		for selected in selected_chars:
			def gen_1(chosen=selected) -> PacketType:
				assert isinstance(chosen, AVGECharacterCard) 
				if len(chosen.energy) == 0:
					return []
				return [AVGEEnergyTransfer(
						chosen.energy[0],
						chosen,
						chosen.env,
						ActionTypes.NONCHAR,
						card,
						None,
					)]
			packet.append(gen_1)

		cards_to_shuffle = list(discard)
		if(len(cards_to_shuffle) > 4):
			cards_to_shuffle = random.sample(cards_to_shuffle, 4)
		for card_to_shuffle in cards_to_shuffle:
			def gen(chosen=card_to_shuffle) -> PacketType:
				return [TransferCard(
					chosen,
					discard,
					deck,
					ActionTypes.NONCHAR,
					card,
					None,
					random.randint(0, len(deck)),
					)]
			packet.append(
				gen
			)

		card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, DressRehearsalRoster)))
		return self.generic_response(card)
