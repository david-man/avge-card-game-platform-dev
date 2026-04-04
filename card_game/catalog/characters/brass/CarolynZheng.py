from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.avge_abstracts.AVGEEnvironment import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import *

_LAST_ROUND_USED_KEY = "carolyn-last-round-atkd"
class _CarolynAttackTracker(AVGEAssessor):
    def __init__(self, owner_card : AVGECharacterCard):
        super().__init__(identifier=(owner_card, AVGEEventListenerType.PASSIVE), group=EngineGroup.EXTERNAL_PRECHECK_1)
        self.owner_card = owner_card
    def event_match(self, event : PlayCharacterCard):
        return isinstance(event, PlayCharacterCard) and event.caller_card == self.owner_card and event.card_action in [ActionTypes.ATK_1, ActionTypes.ATK_2]
    def event_effect(self):
        return True
    def update_status(self):
        return
    def make_announcement(self):
        return False
    def package(self):
        return ""
    def on_packet_completion(self):
        return
    def assess(self, args=None):
        self.owner_card.env.cache.set(self.owner_card, _LAST_ROUND_USED_KEY, self.owner_card.env.round_id)
        return self.generate_response()

class _CarolynAttackModifier(AVGEModifier):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=(owner_card, AVGEEventListenerType.PASSIVE), group=EngineGroup.EXTERNAL_MODIFIERS_2)
        self.owner_card = owner_card

    def event_match(self, event):
        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]:
            return False
        if(not isinstance(event.caller_card, AVGECharacterCard)):
            return False
        if event.caller_card != self.owner_card:
            return False
        if event.target_card.player != self.owner_card.player.opponent:
            return False
        last_round_played = self.owner_card.env.cache.get(self.owner_card, _LAST_ROUND_USED_KEY, None)
        return last_round_played is None or (last_round_played < self.owner_card.player.get_last_turn())

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return True

    def package(self):
        return "CarolynZheng Next Attack Modifier"

    def on_packet_completion(self):
        return
    
    def modify(self, args=None):
        event : AVGECardHPChange = self.attached_event
        # increase damage by 30 (damage is negative change_amount)
        event.modify_magnitude(30)
        return self.generate_response()


class CarolynZheng(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.BRASS, 1)
        self.has_atk_1 = True
        self.atk_1_cost = 1
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(caller_card : AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        # attach turn-start reactor to evaluate previous turn
        caller_card.add_listener(_CarolynAttackTracker(caller_card))
        caller_card.add_listener(_CarolynAttackModifier(caller_card))
        return caller_card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import AVGECardHPChange
        packet = [AVGECardHPChange(
                lambda : card.player.opponent.get_active_card(),
                70,
                AVGEAttributeModifier.SUBSTRACTIVE,
                ActionTypes.ATK_1,
                CardType.BRASS,
                card,
            )]
        card.propose(packet)
        return card.generate_response()

