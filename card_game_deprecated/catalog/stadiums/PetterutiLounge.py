from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup

from card_game.internal_events import AVGECardHPChange, EmptyEvent, TransferCard


class PetterutiMaidDamageModifier(AVGEModifier):
	def __init__(self, owner_card: AVGEStadiumCard):
		super().__init__(
			identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, PetterutiLounge),
			group=EngineGroup.EXTERNAL_MODIFIERS_2,
		)
		self.owner_card = owner_card

	def event_match(self, event):
		if(not self.owner_card._is_active_stadium()):
			return False
		if(not isinstance(event, AVGECardHPChange)):
			return False
		if(event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE):
			return False
		if(event.change_type == CardType.ALL):
			return False
		if(event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]):
			return False
		if(not isinstance(event.caller, AVGECharacterCard)):
			return False
		return len(event.caller.statuses_attached.get(StatusEffect.MAID, [])) > 0

	def event_effect(self) -> bool:
		return True

	def update_status(self):
		if(not self.owner_card._is_active_stadium()):
			self.invalidate()

	def modify(self, args=None):
		event = self.attached_event
		assert isinstance(event, AVGECardHPChange)
		event.modify_magnitude(10)
		return Response(ResponseType.ACCEPT, Data())
	
	def __str__(self):
		return "Petteruti Lounge: Matcha Maid Cafe, +10 Damage"


class PetterutiMaidTransfer(AVGEModifier):
	def __init__(self, owner_card: AVGEStadiumCard):
		super().__init__(
			identifier=AVGEEngineID(owner_card, ActionTypes.NONCHAR, PetterutiLounge),
			group=EngineGroup.EXTERNAL_MODIFIERS_1,
		)
		self.owner_card = owner_card

	def event_match(self, event):
		
		if(not self.owner_card._is_active_stadium()):
			return False
		if(not isinstance(event, TransferCard)):
			return False
		if(not isinstance(event.card, AVGECharacterCard)):
			return False
		if(not (event.pile_from.pile_type == Pile.ACTIVE and event.pile_to.pile_type == Pile.BENCH)):
			return False
		if(event.energy_requirement == 0):
			return False
		return len(event.card.statuses_attached.get(StatusEffect.MAID, [])) > 0

	def event_effect(self) -> bool:
		return True

	def update_status(self):
		if(not self.owner_card._is_active_stadium()):
			self.invalidate()

	def modify(self, args=None):
		event = self.attached_event
		assert isinstance(event, TransferCard)
		event.energy_requirement = max(0, event.energy_requirement - 1)
		return Response(ResponseType.ACCEPT, Notify("Petteruti Lounge: Matcha Maid Cafe reduced the retreat cost", all_players, default_timeout))
	
	def __str__(self):
		return "Petteruti Lounge: Matcha Maid Cafe"


class PetterutiPowerpointNightPacketListener(AVGEPacketListener):
	def __init__(self, owner_card: AVGEStadiumCard):
		super().__init__(
			identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, PetterutiLounge),
		)
		self.owner_card = owner_card

	def packet_match(self, packet: AVGEPacket, packet_finish_status: ResponseType) -> bool:
		if(not self.owner_card._is_active_stadium()):
			return False
		if(not isinstance(packet.identifier.caller, AVGECharacterCard)):
			return False
		return packet.identifier.action_type in [ActionTypes.ATK_1, ActionTypes.ATK_2]

	def update_status(self):
		if(not self.owner_card._is_active_stadium()):
			self.invalidate()

	def react(self, p: AVGEPacket) -> Response:
		caller = p.identifier.caller
		assert isinstance(caller, AVGECharacterCard)
		attacking_player = caller.player
		opponent_hand = attacking_player.opponent.cardholders[Pile.HAND]
		if(len(opponent_hand) == 0):
			return Response(ResponseType.ACCEPT, Data())

		revealed = random.choice(list(opponent_hand))
		return Response(ResponseType.ACCEPT, RevealCards('Petteruti Lounge Powerpoint Night: Random card from opponent hand', [attacking_player.unique_id], default_timeout, [revealed]))


class PetterutiLounge(AVGEStadiumCard):
	def __init__(self, unique_id):
		super().__init__(unique_id)

	def play_card(self) -> Response:
		self.add_listener(PetterutiMaidDamageModifier(self))
		self.add_listener(PetterutiMaidTransfer(self))
		self.add_packet_listener(PetterutiPowerpointNightPacketListener(self))

		return Response(ResponseType.CORE, Data())
