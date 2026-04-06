from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEConstrainer import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup

class GoonStatusTransferModifier(AVGEModifier):
	def __init__(self):
		super().__init__(
			identifier=(None, ActionTypes.ENV),
			group=EngineGroup.EXTERNAL_MODIFIERS_1,
		)
	def event_match(self, event):
		from card_game.internal_events import TransferCard

		return (
			isinstance(event, TransferCard)
			and isinstance(event.card, AVGECharacterCard)
			and len(event.card.statuses_attached.get(StatusEffect.GOON, [])) > 0
			and event.pile_from.pile_type == Pile.ACTIVE
			and event.pile_to.pile_type == Pile.BENCH
			and event.energy_requirement > 0
		)
	def event_effect(self) -> bool:
		return True

	def update_status(self):
		return

	def make_announcement(self) -> bool:
		return True

	def package(self):
		return "Goon Retreat Cost Modifier"
	
	def modify(self, args = {}):
		self.attached_event.energy_requirement += 1

class GoonStatusChangeReactor(AVGEReactor):
	def __init__(self):
		super().__init__(
			identifier=(None, ActionTypes.ENV),
			group=EngineGroup.EXTERNAL_REACTORS,
		)

	def event_match(self, event):
		from card_game.internal_events import AVGECardStatusChange

		return (
			isinstance(event, AVGECardStatusChange)
			and event.status_effect == StatusEffect.GOON
			and isinstance(event.target, AVGECharacterCard)
		)

	def event_effect(self) -> bool:
		return True

	def update_status(self):
		return

	def make_announcement(self) -> bool:
		return True

	def package(self):
		return "Goon On Status Change Reactor"

	def react(self, args={}):
		from card_game.internal_events import AVGECardHPChange, AVGECardMaxHPChange, AVGECardStatusChange

		event: AVGECardStatusChange = self.attached_event
		target = event.target
		if(not isinstance(target, AVGECharacterCard)):
			return self.generate_response()

		packet = []
		caller_card = event.caller_card if event.caller_card is not None else target

		if(event.change_type == StatusChangeType.ADD and len(event.target.statuses_attached.get(StatusEffect.GOON, [])) == 1):
			packet.extend([
				AVGECardMaxHPChange(target, 20, AVGEAttributeModifier.ADDITIVE, ActionTypes.ENV, caller_card),
				AVGECardHPChange(target, 20, AVGEAttributeModifier.ADDITIVE, CardType.ALL, ActionTypes.ENV, caller_card),
			])
		elif(event.change_type == StatusChangeType.REMOVE and len(event.target.statuses_attached.get(StatusEffect.GOON, [])) == 0):
			packet.extend([
				AVGECardMaxHPChange(target, 20, AVGEAttributeModifier.SUBSTRACTIVE, ActionTypes.PASSIVE, caller_card, None),
			])

		if(len(packet) > 0):
			self.propose(packet)
		return self.generate_response()


class GoonFoldingStandAttackModifier(AVGEModifier):
	def __init__(self, owner_card: AVGEItemCard, round_played):
		super().__init__(
			identifier=(owner_card, ActionTypes.NONCHAR),
			group=EngineGroup.EXTERNAL_MODIFIERS_2,
		)
		self.owner_card = owner_card
		self.round_played = round_played

	def event_match(self, event):
		from card_game.internal_events import AVGECardHPChange

		if(not isinstance(event, AVGECardHPChange)):
			return False
		if(event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE):
			return False
		if(event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]):
			return False
		if(not isinstance(event.caller_card, AVGECharacterCard)):
			return False
		if(event.caller_card.player != self.owner_card.player):
			return False
		if(event.caller_card != self.owner_card.player.get_active_card()):
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
		if(self.owner_card.env is None or self.owner_card.env.round_id != self.round_played):
			self.invalidate()

	def make_announcement(self) -> bool:
		return True

	def package(self):
		return "Goon BUOStand Modifier"

	def on_packet_completion(self):
		self.invalidate()
	def modify(self, args={}):
		event = self.attached_event
		event.modify_magnitude(20)
		return self.generate_response()


class GoonBUOStandAttackModifier(AVGEModifier):
	def __init__(self, owner_card: AVGEItemCard, round_played):
		super().__init__(
			identifier=(owner_card, ActionTypes.NONCHAR),
			group=EngineGroup.EXTERNAL_MODIFIERS_2,
		)
		self.owner_card = owner_card
		self.round_played = round_played

	def event_match(self, event):
		from card_game.internal_events import AVGECardHPChange

		if(not isinstance(event, AVGECardHPChange)):
			return False
		if(event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE):
			return False
		if(event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]):
			return False
		if(not isinstance(event.caller_card, AVGECharacterCard)):
			return False
		if(event.caller_card.player != self.owner_card.player):
			return False
		if(event.caller_card != self.owner_card.player.get_active_card()):
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
		if(self.owner_card.env is None or self.owner_card.env.round_id != self.round_played):
			self.invalidate()

	def make_announcement(self) -> bool:
		return True

	def package(self):
		return "Goon FoldingStand Modifier"

	def on_packet_completion(self):
		self.invalidate()
	def modify(self, args={}):
		event = self.attached_event
		event.modify_magnitude(30)
		return self.generate_response()


class GoonStandAttackModifierConstraint(AVGEConstraint):
	def __init__(self):
		super().__init__((None, AVGEConstrainerType.ENV))

	def _caller_has_goon(self, event) -> bool:
		from card_game.internal_events import AVGECardHPChange
		if(event is None or not isinstance(event, AVGECardHPChange)):
			return False
		if(not isinstance(event.caller_card, AVGECharacterCard)):
			return False
		return len(event.caller_card.statuses_attached.get(StatusEffect.GOON, [])) > 0

	def match(self, obj: AVGEAbstractEventListener | AVGEConstraint):
		from card_game.catalog.items.BUOStand import BUOStandNextAttackModifier
		from card_game.catalog.items.FoldingStand import FoldingStandNextAttackModifier

		if(not isinstance(obj, AVGEAbstractEventListener)):
			return False

		event = obj.attached_event
		if(not self._caller_has_goon(event)):
			return False

		if(isinstance(obj, FoldingStandNextAttackModifier)):
			event.attach_listener(GoonFoldingStandAttackModifier(obj.owner_card, obj.round_played))
			return True
		if(isinstance(obj, BUOStandNextAttackModifier)):
			event.attach_listener(GoonBUOStandAttackModifier(obj.owner_card, obj.round_played))
			return True
		return False

	def update_status(self):
		return

	def make_announcement(self) -> bool:
		return True

	def package(self):
		return "Goon Stand Modifier Constraint"
