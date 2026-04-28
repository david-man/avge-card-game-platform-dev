from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import AVGECardHPChange, InputEvent


class AnnaBrownBenchDamageShield(AVGEAssessor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, AnnaBrown), group=EngineGroup.EXTERNAL_MODIFIERS_2)
        self.owner_card = owner_card

    def event_match(self, event):
        if not isinstance(event, AVGECardHPChange):
            return False
        if event.change_type == CardType.ALL:
            return False
        if event.target_card != self.owner_card:
            return False
        if self.owner_card.cardholder is None or self.owner_card.cardholder.pile_type != Pile.BENCH:
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
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

    def assess(self, args=None):
        if args is None:
            args = {}
        event = self.attached_event
        assert isinstance(event, AVGECardHPChange)
        return Response(ResponseType.FAST_FORWARD, Notify('Do Not Disturb: Benched Anna Brown ignores damage from opponent attacks.', all_players, default_timeout))


class AnnaBrown(AVGECharacterCard):
    _D6_KEY = 'annabrown_d6_roll'

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.WOODWIND, 2, 3, 0)
        self.has_passive = True
        self.atk_1_name = 'Hyper-Ventilation!'

    def passive(self) -> Response:
        self.add_listener(AnnaBrownBenchDamageShield(self))
        return Response(ResponseType.CORE, Data())

    def atk_1(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        missing = object()
        roll = card.env.cache.get(card, AnnaBrown._D6_KEY, missing, True)
        if roll is missing:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [AnnaBrown._D6_KEY],
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            D6Data('Hyper-Ventilation!: Roll a D6.')
                        )
                    ]),
            )

        if not isinstance(roll, int):
            return self.generic_response(card, ActionTypes.ATK_2)

        damage = 30 + (10 * int(roll))

        def gen() -> PacketType:
            packet: PacketType = []
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        damage,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.WOODWIND,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )
            return packet

        card.propose(AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_1, AnnaBrown)))
        return self.generic_response(card, ActionTypes.ATK_1)
