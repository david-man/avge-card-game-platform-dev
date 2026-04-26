from __future__ import annotations

from card_game.avge_abstracts import *

from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import AVGECardHPChange, TransferCard

class AlumnaeHallDrawPunishReactor(AVGEReactor):
	def __init__(self, owner_card: AVGEStadiumCard):
		super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, AlumnaeHall), group=EngineGroup.EXTERNAL_REACTORS)
		self.owner_card = owner_card

	def event_match(self, event):
		if(not self.owner_card._is_active_stadium()):
			return False
		if(not isinstance(event, TransferCard)):
			return False
		if(event.pile_from.pile_type != Pile.DECK or event.pile_to.pile_type != Pile.HAND):
			return False
		if(event.card is None or event.card.player is None):
			return False
		return True

	def event_effect(self) -> bool:
		return True

	def update_status(self):
		if(not self.owner_card._is_active_stadium()):
			self.invalidate()

	def react(self, args=None):
		event = self.attached_event
		assert isinstance(event, TransferCard)
		target_player : AVGEPlayer = event.card.player
		def gen() -> PacketType:
			packet : PacketType = []
			for character in target_player.get_cards_in_play():
				current_hp = character.hp
				nonlethal_damage = max(0, min(current_hp - 1, 10))
				packet.append(
					AVGECardHPChange(
						character,
						nonlethal_damage,
						AVGEAttributeModifier.SUBSTRACTIVE,
						CardType.ALL,
						ActionTypes.NONCHAR,
						None,
						self.owner_card,
					)
				)
			return packet

		self.propose(AVGEPacket([gen], AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, AlumnaeHall)), 1)
		return Response(ResponseType.ACCEPT, Notify('Alumnae Hall: Draw trigger applied nonlethal damage to the drawing player\'s in-play characters.', all_players, default_timeout))


class AlumnaeHall(AVGEStadiumCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self) -> Response:
		packet = []
		if(self.env.round_id > 0):
			for player in self.env.players.values():
				hand = player.cardholders[Pile.HAND]
				discard = player.cardholders[Pile.DISCARD]
				for held_card in list(hand):
					if(isinstance(held_card, AVGEItemCard)):
						packet.append(
							TransferCard(
								held_card,
								hand,
								discard,
								ActionTypes.NONCHAR,
								self,
								None,
							)
						)

		self.add_listener(AlumnaeHallDrawPunishReactor(self))
		if(len(packet) > 0):
			self.propose(AVGEPacket(packet, AVGEEngineID(self, ActionTypes.NONCHAR, AlumnaeHall)))
		return Response(ResponseType.CORE, Data())
