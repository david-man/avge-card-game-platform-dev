from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import AVGECardHPChange, EmptyEvent


class JordanOpponentAttackBoost(AVGEModifier):
    def __init__(self, owner_card: AVGECharacterCard, round_active: int):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.ATK_1, JordanRoosevelt), group=EngineGroup.EXTERNAL_MODIFIERS_2)
        self.owner_card = owner_card
        self.round_active = round_active

    def event_match(self, event):
        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]:
            return False
        if not isinstance(event.caller, AVGECharacterCard):
            return False
        if event.caller.player != self.owner_card.player.opponent:
            return False
        return self.owner_card.env.round_id == self.round_active

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        if self.owner_card.env.round_id > self.round_active:
            self.invalidate()

    def modify(self, args=None):
        if args is None:
            args = {}
        event = self.attached_event
        assert isinstance(event, AVGECardHPChange)
        event.modify_magnitude(20)
        return Response(ResponseType.ACCEPT, Notify('Trickster: Opponent attack +20 this turn.', all_players, default_timeout))
    
    def __str__(self):
        return "Jordan Roosevelt: Trickster Buff"


class JordanSelfAttackBoost(AVGEModifier):
    def __init__(self, owner_card: AVGECharacterCard, round_active: int):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.ATK_1, JordanRoosevelt), group=EngineGroup.EXTERNAL_MODIFIERS_2)
        self.owner_card = owner_card
        self.round_active = round_active

    def event_match(self, event):
        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]:
            return False
        if event.caller != self.owner_card:
            return False
        return self.owner_card.env.round_id == self.round_active

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        if self.owner_card.env.round_id > self.round_active:
            self.invalidate()

    def modify(self, args=None):
        if args is None:
            args = {}
        event = self.attached_event
        assert isinstance(event, AVGECardHPChange)
        event.modify_magnitude(60)
        return Response(ResponseType.ACCEPT, Notify('Trickster: Jordan attack +60 this turn.', all_players, default_timeout))
    
    def __str__(self):
        return "Jordan Roosevelt: Trickster Buff"


class JordanRoosevelt(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.WOODWIND, 1, 1, 2)
        self.atk_1_name = 'Trickster'
        self.atk_2_name = 'Sparkling Run'

    def atk_1(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        next_opp_round = card.player.opponent.get_next_turn()
        next_player_round = card.player.get_next_turn()
        card.add_listener(JordanOpponentAttackBoost(card, next_opp_round))
        card.add_listener(JordanSelfAttackBoost(card, next_player_round))
        packet : PacketType = []
        packet.append(EmptyEvent(
                ActionTypes.ATK_1,
                card,
                ResponseType.CORE,
                self.generic_response(card, ActionTypes.ATK_1).data
            ))
        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, JordanRoosevelt)))
        return Response(ResponseType.CORE, Data())

    def atk_2(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        def generate_packet() -> PacketType:
            packet: PacketType = []
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        30,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.WOODWIND,
                        ActionTypes.ATK_2,
                        None,
                        card,
                    )
                )
            packet.append(
                AVGECardHPChange(
                    card,
                    20,
                    AVGEAttributeModifier.ADDITIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_2,
                    None,
                    card,
                )
            )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_2, JordanRoosevelt)))
        return self.generic_response(card, ActionTypes.ATK_2)
