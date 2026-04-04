from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class AVGEBirbNextTurnDamageModifier(AVGEModifier):
	def __init__(self, owner_card: AVGEItemCard):
		super().__init__(identifier=(owner_card, AVGEEventListenerType.NONCHAR), group=EngineGroup.EXTERNAL_MODIFIERS_2)
		self.owner_card = owner_card

	def event_match(self, event):
		from card_game.internal_events import AVGECardHPChange

		if(not isinstance(event, AVGECardHPChange)):
			return False
		if(event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE):
			return False
		if(event.catalyst_action in [ActionTypes.ATK_1, ActionTypes.ATK_2]):
			return False
		if not isinstance(event.caller_card, Card):
			return False
		if(event.caller_card.player != self.owner_card.player.opponent):
			return False
		return True

	def event_effect(self) -> bool:
		return True

	def update_status(self):
		round_used = self.owner_card.env.cache.get(self.owner_card, AVGEBirb._ROUND_USED_KEY, 0)
		if(self.owner_card.env.round_id > round_used):
			self.invalidate()

	def make_announcement(self) -> bool:
		return True

	def package(self):
		return "AVGEBirb Modifier"

	def modify(self, args={}):
		event = self.attached_event
		event.modify_magnitude(20)
		self.invalidate()
		return self.generate_response()

class AVGEBirb(AVGEItemCard):
	_ROUND_USED_KEY = "avgebirb_round_used"

	def __init__(self, unique_id):
		super().__init__(unique_id)

	
	
	@staticmethod
	def play_card(card_for: AVGECharacterCard, parent_event: AVGEEvent, args: Data = None) -> Response:
		from card_game.internal_events import TransferCard, AVGEStatusChange

		opponent = card_for.player.opponent
		opponent_discard = opponent.cardholders[Pile.DISCARD]
		card_for.env.cache.set(card_for, AVGEBirb._ROUND_USED_KEY, card_for.env.round_id)

		damage_modifier = AVGEBirbNextTurnDamageModifier(card_for)
		card_for.add_listener(damage_modifier)
		def generate_packet():
			packet = []
			for character in card_for.player.opponent.get_cards_in_play():
				for tool in list(character.tools_attached):
					packet.append(
						TransferCard(
							tool,
							character.tools_attached,
							opponent_discard,
							ActionTypes.NONCHAR,
							card_for,
						)
					)

				for status, holders in list(character.statuses_attached.items()):
					for holder in list(holders):
						packet.append(
							AVGEStatusChange(
								character,
								status,
								StatusChangeType.REMOVE,
								ActionTypes.NONCHAR,
								holder,
							)
						)
			return packet
		card_for.propose(generate_packet)
		return card_for.generate_response()
