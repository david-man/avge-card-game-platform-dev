from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.catalog.items.AVGEBirb import AVGEBirb
from card_game.internal_events import AVGECardHPChange, InputEvent, TransferCard

class RaffleTicket(AVGEItemCard):
	_HEAL_TARGET_KEY = 'raffleticket_heal_target'

	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self, card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:
		player = card.player
		deck = player.cardholders[Pile.DECK]
		hand = player.cardholders[Pile.HAND]

		if(len(deck) == 0):
			return Response(ResponseType.SKIP, Notify('RaffleTicket: No cards in deck to draw.', [player.unique_id], default_timeout))
		bottom_card = list(deck)[-1]

		heal_target = None
		if(isinstance(bottom_card, AVGEBirb)):
			targets = [c for c in card.player.get_cards_in_play() if isinstance(c, AVGECharacterCard)]
			missing = object()
			target = card.env.cache.get(card, RaffleTicket._HEAL_TARGET_KEY, missing, one_look=True)
			if(target is missing):
				return Response(
					ResponseType.INTERRUPT,
					Interrupt[AVGEEvent]([
							InputEvent(
								player,
								[RaffleTicket._HEAL_TARGET_KEY],
								lambda res : True,
								ActionTypes.NONCHAR,
								card,
								CardSelectionQuery('Raffle Ticket: Choose one character to heal.', targets, targets, False, False)
							)
						]),
				)
			if not isinstance(target, AVGECharacterCard) or target not in targets:
				raise Exception('RaffleTicket: Invalid heal target selection')
			heal_target = target

		packet: PacketType = [
			TransferCard(
				bottom_card,
				deck,
				hand,
				ActionTypes.NONCHAR,
				card,
				None,
			)
		]

		if isinstance(heal_target, AVGECharacterCard):
			packet.append(
				AVGECardHPChange(
					heal_target,
					heal_target.max_hp,
					AVGEAttributeModifier.SET_STATE,
					CardType.ALL,
					ActionTypes.NONCHAR,
					None,
					card,
				)
			)

		card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, RaffleTicket)))
		return self.generic_response(card)
