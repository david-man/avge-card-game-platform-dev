from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class AVGEBirbNextTurnDamageModifier(AVGEModifier):
	def __init__(self, owner_card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard, round_active : int = 0):
		super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.NONCHAR, AVGEBirb), group=EngineGroup.EXTERNAL_MODIFIERS_2)
		self.owner_card = owner_card
		self.round_active = round_active

	def event_match(self, event):
		from card_game.internal_events import AVGECardHPChange

		if(not isinstance(event, AVGECardHPChange)):
			return False
		if(event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE):
			return False
		if(event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]):
			return False
		if not isinstance(event.caller_card, AVGECard):
			return False
		if(event.caller_card.player != self.owner_card.player.opponent):
			return False
		if(event.caller_card.env.round_id != self.round_active):
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
		from card_game.internal_events import AVGECardHPChange
		assert isinstance(event, AVGECardHPChange)
		event.modify_magnitude(20)
		return self.generate_response()

class AVGEBirb(AVGEItemCard):

	def __init__(self, unique_id):
		super().__init__(unique_id)
	
	@staticmethod
	def play_card(card) -> Response:
		from card_game.internal_events import TransferCard, AVGECardStatusChange

		opponent = card.player.opponent
		opponent_discard = opponent.cardholders[Pile.DISCARD]
		damage_modifier = AVGEBirbNextTurnDamageModifier(card, card.player.opponent.get_next_turn())
		card.env.add_listener(damage_modifier)
		def generate_packet():
			packet = []
			for character in card.player.opponent.get_cards_in_play():
				for tool in list(character.tools_attached):
					packet.append(
						TransferCard(
							tool,
							character.tools_attached,
							opponent_discard,
							ActionTypes.NONCHAR,
							card,
						)
					)

				for status, holders in list(character.statuses_attached.items()):
					for holder in list(holders):
						packet.append(
							AVGECardStatusChange(
								status,
								StatusChangeType.REMOVE,
								character,
								ActionTypes.NONCHAR,
								holder,
							)
						)
			return packet
		card.propose(AVGEPacket(generate_packet(), AVGEEngineID(card, ActionTypes.NONCHAR, AVGEBirb)))
		return card.generate_response()
