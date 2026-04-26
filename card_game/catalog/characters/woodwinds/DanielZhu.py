from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import AVGECardHPChange, InputEvent


class DanielZhuSharePainModifier(AVGEModifier):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, DanielZhu), group=EngineGroup.EXTERNAL_MODIFIERS_2)
        self.owner_card = owner_card

    def event_match(self, event):
        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if event.change_type == CardType.ALL:
            return False
        if event.target_card == self.owner_card:
            return False
        if event.target_card.player != self.owner_card.player:
            return False
        if self.owner_card.cardholder is None or self.owner_card.cardholder.pile_type not in [Pile.ACTIVE, Pile.BENCH]:
            return False
        if self.owner_card.hp <= 1:
            return False
        return True

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def modify(self, args=None):
        if args is None:
            args = {}
        event = self.attached_event
        assert isinstance(event, AVGECardHPChange)

        incoming_damage = int(event.magnitude)
        max_redirect = min(30, incoming_damage, self.owner_card.hp - 1)
        if max_redirect <= 0:
            return Response(ResponseType.ACCEPT, Data())

        redirect_amount = self.owner_card.env.cache.get(self.owner_card, DanielZhu._REDIRECT_KEY, None, True)
        if redirect_amount is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            self.owner_card.player,
                            [DanielZhu._REDIRECT_KEY],
                            lambda r: True,
                            ActionTypes.PASSIVE,
                            self.owner_card,
                            IntegerInputData("Share the Pain: Redirect Damage Quantity", 0, max_redirect)
                        )
                    ]),
            )

        if not isinstance(redirect_amount, int):
            return Response(ResponseType.ACCEPT, Data())

        redirect_damage = max(0, min(max_redirect, int(redirect_amount)))
        if redirect_damage <= 0:
            return Response(ResponseType.ACCEPT, Notify('Share the Pain: Redirected 0 damage to Daniel Zhu.', all_players, default_timeout))

        event.modify_magnitude(-redirect_damage)

        self.owner_card.propose(
            AVGEPacket([
                AVGECardHPChange(
                    self.owner_card,
                    redirect_damage,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.PASSIVE,
                    None,
                    self.owner_card,
                )
            ], AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, DanielZhu))
        )

        return Response(
            ResponseType.ACCEPT,
            Notify(f'Share the Pain: Redirected {redirect_damage} damage to Daniel Zhu.', all_players, default_timeout),
        )


class DanielZhu(AVGECharacterCard):
    _D6_ROLL_KEY = 'danielzhu_d6_roll'
    _REDIRECT_KEY = 'danielzhu_damage_redirect'

    def __init__(self, unique_id):
        super().__init__(unique_id, 120, CardType.WOODWIND, 2, 0, 3)
        self.has_passive = True
        self.atk_1_name = 'Hyper-Ventilation!'

    def passive(self) -> Response:
        self.add_listener(DanielZhuSharePainModifier(self))
        return Response(ResponseType.CORE, Data())

    def atk_1(self, card: AVGECharacterCard) -> Response:
        missing = object()
        roll = card.env.cache.get(card, DanielZhu._D6_ROLL_KEY, missing, True)
        if roll is missing:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [DanielZhu._D6_ROLL_KEY],
                            lambda r: True,
                            ActionTypes.ATK_2,
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
                        ActionTypes.ATK_2,
                        None,
                        card,
                    )
                )
            return packet

        card.propose(AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_2, DanielZhu)))
        return self.generic_response(card, ActionTypes.ATK_2)
