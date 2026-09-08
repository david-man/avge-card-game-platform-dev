from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup

from card_game.internal_events import AVGECardHPChange, AVGEEnergyTransfer


class BUOStandNextAttackModifier(AVGEModifier):
	def __init__(self, owner_card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard, round_played):
		super().__init__(
			identifier=AVGEEngineID(owner_card, ActionTypes.NONCHAR, BUOStand),
			group=EngineGroup.EXTERNAL_MODIFIERS_2,
		)
		self.owner_card = owner_card
		self.round_played = round_played

	def event_match(self, event):
		if(not isinstance(event, AVGECardHPChange)):
			return False
		if(event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE):
			return False
		if(event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]):
			return False
		if(event.caller != self.owner_card.player.get_active_card()):
			return False
		if(not isinstance(event.target_card, AVGECharacterCard)):
			return False
		if(event.target_card.player != self.owner_card.player.opponent):
			return False
		if(event.target_card.env.round_id != self.round_played):
			return False
		return True
	def event_effect(self) -> bool:
		return True
	
	def update_status(self):
		if(self.owner_card.env.round_id > self.round_played):
			self.invalidate()
	
	def on_packet_completion(self):
		self.invalidate()

	def modify(self, args=None):
		event = self.attached_event
		assert isinstance(event, AVGECardHPChange)
		if(isinstance(event.caller, AVGECharacterCard) and len(event.caller.statuses_attached.get(StatusEffect.GOON, [])) > 0):
			event.modify_magnitude(30)
			return Response(ResponseType.ACCEPT, Notify('BUO Stand: +20 (+10[GOON]) damage on your first attack this turn.', all_players, default_timeout))
		else:
			event.modify_magnitude(20)
			return Response(ResponseType.ACCEPT, Notify('BUO Stand: +20 damage on your first attack this turn.', all_players, default_timeout))
	def __str__(self):
		return "BUO Stand Buff"

class BUOStand(AVGEItemCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	def __str__(self):
		return "BUO Stand"
	def play_card(self, card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard) -> Response:
		active = card.player.get_active_card()
		if(len(active.energy) == 0):
			return Response(ResponseType.FAST_FORWARD, Notify('BUOStand: No energy on active character :(', [card.player.unique_id], default_timeout))
		card.add_listener(BUOStandNextAttackModifier(card, card.env.round_id))
		packet: PacketType = [
			AVGEEnergyTransfer(active.energy[0], active, card.env, ActionTypes.NONCHAR, card, None)
		]
		card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.NONCHAR, BUOStand)))
		return self.generic_response(card)
