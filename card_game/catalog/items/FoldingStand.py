from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class FoldingStandNextAttackModifier(AVGEModifier):
    def __init__(self, owner_card: AVGEToolCard | AVGEItemCard | AVGESupporterCard | AVGEStadiumCard | AVGECharacterCard, round_played):
        super().__init__(
            identifier=AVGEEngineID(owner_card, ActionTypes.NONCHAR, FoldingStand),
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

    def modify(self, args=None):
        event = self.attached_event
        from card_game.internal_events import AVGECardHPChange
        assert isinstance(event, AVGECardHPChange)
        dmg = 10
        if(isinstance(event.caller_card, AVGECharacterCard) and len(event.caller_card.statuses_attached[StatusEffect.GOON]) > 0):
            dmg = 20
        event.modify_magnitude(dmg)
        return self.generate_response()


class FoldingStand(AVGEItemCard):
    def __init__(self, unique_id):
        super().__init__(unique_id)
    @staticmethod
    def play_card(card) -> Response:
        round_played = card.env.round_id
        next_attack_modifier = FoldingStandNextAttackModifier(card, round_played)
        card.add_listener(next_attack_modifier)
        return card.generate_response()
