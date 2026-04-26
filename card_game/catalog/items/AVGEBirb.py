from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import AVGECardHPChange, AVGECardStatusChange, TransferCard


class AVGEBirbNextTurnDamageModifier(AVGEModifier):
	def __init__(self, owner_card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard, round_active : int):
		super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.NONCHAR, AVGEBirb), group=EngineGroup.EXTERNAL_MODIFIERS_2)
		self.owner_card = owner_card
		self.round_active = round_active

	def event_match(self, event):
		if(not isinstance(event, AVGECardHPChange)):
			return False
		if(event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE):
			return False
		if(event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]):
			return False
		if not isinstance(event.target_card, AVGECharacterCard):
			return False
		if(event.target_card.player != self.owner_card.player):
			return False
		if(event.target_card != self.owner_card.player.get_active_card()):
			return False
		if(self.owner_card.env.round_id != self.round_active):
			return False
		return True

	def event_effect(self) -> bool:
		return True

	def update_status(self):
		if(self.owner_card.env.round_id > self.round_active):
			self.invalidate()

	def make_announcement(self) -> bool:
		return True

	def package(self):
		return "AVGEBirb Modifier"
	
	def on_packet_completion(self):
		self.invalidate()

	def modify(self, args=None):
		event = self.attached_event
		assert isinstance(event, AVGECardHPChange)
		event.modify_magnitude(20)
		return Response(ResponseType.ACCEPT, Notify('AVGEBirb: Your active takes +20 damage from this attack.', all_players, default_timeout))

class AVGEBirb(AVGEItemCard):

	def __init__(self, unique_id):
		super().__init__(unique_id)
	
	def play_card(self, card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:
		opponent = card.player.opponent
		opponent_discard = opponent.cardholders[Pile.DISCARD]
		damage_modifier = AVGEBirbNextTurnDamageModifier(card, card.player.get_next_turn())
		card.add_listener(damage_modifier)

		def generate_packet() -> PacketType:
			packet: PacketType = []
			for character in card.player.opponent.get_cards_in_play():
				if not isinstance(character, AVGECharacterCard):
					continue
				for tool in list(character.tools_attached):
					packet.append(
						TransferCard(
							tool,
							character.tools_attached,
							opponent_discard,
							ActionTypes.NONCHAR,
							card,
							None,
						)
					)

				for status, holders in character.statuses_attached.items():
					if len(holders) > 0:
						packet.append(
							AVGECardStatusChange(
								status,
								StatusChangeType.REMOVE,
								character,
								ActionTypes.NONCHAR,
								card,
								None,
							)
						)
			return packet

		packet = generate_packet()
		if len(packet) > 0:
			card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, AVGEBirb)))
		return self.generic_response(card)
