from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class FoldingStandNextAttackModifier(AVGEModifier):
    def __init__(self, owner_card: AVGEItemCard, round_played):
        super().__init__(
            identifier=(owner_card, AVGEEventListenerType.NONCHAR),
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
        if(event.caller_card != self.owner_card.player.get_active_card()):
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

    def make_announcement(self) -> bool:
        return True

    def package(self):
        return "FoldingStand Modifier"
    
    def on_packet_completion(self):
        self.invalidate()

    def modify(self, args={}):
        event = self.attached_event
        event.modify_magnitude(10)
        return self.generate_response()


class FoldingStand(AVGEItemCard):
    def __init__(self, unique_id):
        super().__init__(unique_id)

    
    
    @staticmethod
    def play_card(card_for: AVGECharacterCard, parent_event: AVGEEvent, args: Data = None) -> Response:
        round_played = card_for.env.round_id
        next_attack_modifier = FoldingStandNextAttackModifier(card_for, round_played)
        card_for.add_listener(next_attack_modifier)
        return card_for.generate_response()
