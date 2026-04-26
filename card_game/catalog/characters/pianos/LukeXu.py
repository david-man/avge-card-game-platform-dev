from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import *


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
        return Notify('Nullify: Opponent abilities have no effect this turn.', all_players, default_timeout)

    def update_status(self):
        if self.owner_card.env.round_id != self.round_played:
            self.invalidate()

    def package(self):
        return 'LukeXu Nullify Constraint'


class LukeXu(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.PIANO, 1, 3)
        self.atk_1_name = 'Three Hand Technique'
        self.has_passive = True

    def passive(self) -> Response:
        self.add_constrainer(LukeXuPassiveConstraint(self, self.env.round_id))
        return Response(ResponseType.CORE, Data())

    def atk_1(self, card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        def make_hit():
            def hit() -> PacketType:
                active = card.player.opponent.get_active_card()
                packet: PacketType = []
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
            return hit

        card.propose(
            AVGEPacket([
                make_hit(),
                make_hit(),
                make_hit(),
            ], AVGEEngineID(card, ActionTypes.ATK_1, LukeXu))
        )

        return self.generic_response(card, ActionTypes.ATK_1)
