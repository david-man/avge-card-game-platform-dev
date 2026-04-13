from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import *

_BUFF_ROUND_KEY = "carolyn-zheng-buff"
class _CarolynAttackTracker(AVGEAssessor):
    def __init__(self, owner_card : AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, CarolynZheng), group=EngineGroup.EXTERNAL_PRECHECK_1)
        self.owner_card = owner_card
    def event_match(self, event : AVGEEvent):
        return isinstance(event, PlayCharacterCard) and event.caller_card == self.owner_card and event.card_action in [ActionTypes.ATK_1, ActionTypes.ATK_2]
    def event_effect(self):
        return True
    def update_status(self):
        return
    def on_packet_completion(self):
        return
    def assess(self, args=None):
        round = self.owner_card.env.cache.get(self.owner_card, _BUFF_ROUND_KEY, None)
        if(round is None or round < self.owner_card.player.get_last_turn()):
            self.owner_card.env.cache.set(self.owner_card, _BUFF_ROUND_KEY, self.owner_card.env.round_id)
        
        return self.generate_response()

class _CarolynAttackModifier(AVGEModifier):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, CarolynZheng), group=EngineGroup.EXTERNAL_MODIFIERS_2)
        self.owner_card = owner_card

    def event_match(self, event):
        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]:
            return False
        if event.caller_card != self.owner_card:
            return False
        if event.target_card.player != self.owner_card.player.opponent:
            return False
        if(event.magnitude == 0):
            return False
        buff_round = self.owner_card.env.cache.get(self.owner_card, _BUFF_ROUND_KEY, None)
        return buff_round is not None and buff_round == self.owner_card.env.round_id

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def on_packet_completion(self):
        return
    
    def modify(self, args=None):
        assert(isinstance(self.attached_event, AVGECardHPChange))
        event : AVGECardHPChange = self.attached_event
        # increase damage by 30 (damage is negative change_amount)
        event.modify_magnitude(30)
        return self.generate_response()


class CarolynZheng(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.BRASS, 1, 0)
        self.has_atk_1 = True
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card : AVGECharacterCard) -> Response:
        # attach turn-start reactor to evaluate previous turn
        card.add_listener(_CarolynAttackTracker(card))
        card.add_listener(_CarolynAttackModifier(card))
        return card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange
        def generate_packet() -> PacketType:
            return [AVGECardHPChange(
                card.player.opponent.get_active_card(),
                70,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.BRASS,
                ActionTypes.ATK_1,
                card,
            )]
        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, CarolynZheng)))
        return card.generate_response()

