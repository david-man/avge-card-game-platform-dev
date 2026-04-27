from __future__ import annotations

import math

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import AVGECardHPChange, TransferCard


class LukeXuPassiveConstraint(AVGEConstraint):
    def __init__(self, owner_card: AVGECharacterCard, round_played: int):
        super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, LukeXu))
        self.owner_card = owner_card
        self.round_played = round_played

    def match(self, obj):
        if not isinstance(obj, AVGEAbstractEventListener) or isinstance(obj, AVGEConstraint):
            return False
        if obj.identifier.action_type not in [ActionTypes.PASSIVE, ActionTypes.ACTIVATE_ABILITY]:
            return False
        listener_owner = obj.identifier.caller
        return isinstance(listener_owner, AVGECharacterCard) and listener_owner.player == self.owner_card.player.opponent

    def response_data_on_attach(self, attached_to) -> Data:
        assert isinstance(attached_to, AVGEAbstractEventListener)
        return Notify(f'Nullify: {str(attached_to.identifier.caller)}\'s ability is disabled this round!', all_players, default_timeout)

    def update_status(self):
        if self.owner_card.env.round_id != self.round_played or self.owner_card.env.player_turn != self.owner_card.player:
            self.invalidate()

    def package(self):
        return 'LukeXu Nullify Constraint'


class _LukeNullifyTransferReactor(AVGEReactor):
    def __init__(self, owner_card: LukeXu):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, LukeXu), group=EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card

    def event_match(self, event):
        if not isinstance(event, TransferCard):
            return False
        owner = self.owner_card
        if owner.player is None:
            return False
        if owner.env.player_turn != owner.player:
            return False
        if event.card != owner:
            return False
        return event.pile_to.pile_type == Pile.ACTIVE and event.pile_to.player == owner.player

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def react(self, args=None):
        if args is None:
            args = {}
        self.owner_card._activate_nullify_for_turn()
        return Response(ResponseType.ACCEPT, Notify('Nullify: Opponent abilities have no effect this turn.', all_players, default_timeout))


class LukeNextAttackHalvedModifier(AVGEModifier):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.ATK_1, LukeXu), group=EngineGroup.EXTERNAL_MODIFIERS_2)
        self.owner_card = owner_card

    def event_match(self, event):
        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if event.change_type == CardType.ALL:
            return False
        if event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]:
            return False
        if not isinstance(event.caller, AVGECharacterCard):
            return False
        return event.caller.player == self.owner_card.player.opponent

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def on_packet_completion(self):
        self.invalidate()

    def modify(self, args=None):
        if args is None:
            args = {}
        event = self.attached_event
        assert isinstance(event, AVGECardHPChange)
        # rounded up halving: x - floor(x/2) == ceil(x/2)
        event.modify_magnitude(-math.floor(event.magnitude / 2))
        return Response(ResponseType.ACCEPT, Notify('Damper Pedal: Incoming damage halved.', all_players, default_timeout))


class LukeXu(AVGECharacterCard):
    _NULLIFY_LISTENER_KEY = 'lukexu_nullify_listener_added'
    _NULLIFY_TURN_KEY = 'lukexu_nullify_turn_applied'

    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.PIANO, 2, 2)
        self.atk_1_name = 'Damper Pedal'
        self.has_passive = True

    def _activate_nullify_for_turn(self):
        current_turn = self.env.round_id
        already = self.env.cache.get(self, LukeXu._NULLIFY_TURN_KEY, None)
        if already == current_turn:
            return
        self.env.cache.set(self, LukeXu._NULLIFY_TURN_KEY, current_turn)
        self.add_constrainer(LukeXuPassiveConstraint(self, current_turn))

    def _moved_to_active_this_turn(self) -> bool:
        if self.player is None:
            return False
        idx = 0
        active_holder = self.player.cardholders[Pile.ACTIVE]
        while True:
            _, found_idx = self.env.check_history(
                self.env.round_id,
                TransferCard,
                {
                    'card': self,
                    'pile_to': active_holder,
                },
                idx,
            )
            if found_idx == -1:
                return False
            return True

    def passive(self) -> Response:
        listener_added = self.env.cache.get(self, LukeXu._NULLIFY_LISTENER_KEY, False)
        if not listener_added:
            self.add_listener(_LukeNullifyTransferReactor(self))
            self.env.cache.set(self, LukeXu._NULLIFY_LISTENER_KEY, True)

        if self.env.player_turn == self.player and self._moved_to_active_this_turn():
            self._activate_nullify_for_turn()

        return Response(ResponseType.CORE, Data())

    def atk_1(self, card: AVGECharacterCard) -> Response:
        def hit() -> PacketType:
            active = card.player.opponent.get_active_card()
            packet: PacketType = []
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        20,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.PIANO,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )
            return packet

        card.propose(
            AVGEPacket([hit], AVGEEngineID(card, ActionTypes.ATK_1, LukeXu))
        )

        card.add_listener(LukeNextAttackHalvedModifier(card))
        return self.generic_response(card, ActionTypes.ATK_1)
