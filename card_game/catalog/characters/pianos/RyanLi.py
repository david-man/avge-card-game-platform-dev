from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import AVGECardHPChange, PlayCharacterCard


class RyanLiMaidDamageModifier(AVGEModifier):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.NONCHAR, RyanLi), group=EngineGroup.EXTERNAL_MODIFIERS_2)
        self.owner_card = owner_card

    def event_match(self, event):
        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]:
            return False
        if not isinstance(event.caller, AVGECharacterCard):
            return False

        caller = event.caller
        if caller.player != self.owner_card.player:
            return False
        return len(caller.statuses_attached.get(StatusEffect.MAID, [])) > 0

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def modify(self, args=None):
        if args is None:
            args = {}
        event = self.attached_event
        assert isinstance(event, AVGECardHPChange)
        event.modify_magnitude(10)
        return Response(ResponseType.ACCEPT, Notify('Moe moe kyun~!: +10 damage for your maid.', all_players, default_timeout))


class RyanLi(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.PIANO, 1, 1, 2)
        self.atk_1_name = 'Separate Hands'
        self.has_passive = True

    def passive(self) -> Response:
        self.add_listener(RyanLiMaidDamageModifier(self))
        return Response(ResponseType.CORE, Data())

    def atk_1(self, card: AVGECharacterCard) -> Response:
        _, used_last_turn_idx = card.env.check_history(
            card.player.get_last_turn(),
            PlayCharacterCard,
            {
                'card': card,
                'card_action': ActionTypes.ATK_1,
                'caller': card,
            },
        )
        if used_last_turn_idx != -1:
            def generate_packet() -> PacketType:
                active = card.player.opponent.get_active_card()
                packet: PacketType = []
                if isinstance(active, AVGECharacterCard):
                    packet.append(
                        AVGECardHPChange(
                            active,
                            40,
                            AVGEAttributeModifier.SUBSTRACTIVE,
                            CardType.PIANO,
                            ActionTypes.ATK_1,
                            None,
                            card,
                        )
                    )
                return packet

            card.propose(
                AVGEPacket([
                    generate_packet
                ], AVGEEngineID(card, ActionTypes.ATK_1, RyanLi))
            )

        return self.generic_response(card, ActionTypes.ATK_1)
