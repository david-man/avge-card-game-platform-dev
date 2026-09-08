from __future__ import annotations

from card_game.avge_abstracts import *

from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import AVGECardHPChange


class _WestonRightBackAtYouReactor(AVGEReactor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(
            identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, WestonPoe),
            group=EngineGroup.EXTERNAL_REACTORS,
        )
        self.owner_card = owner_card

    def event_match(self, event):
        if not isinstance(event, AVGECardHPChange):
            return False
        if event.target_card != self.owner_card:
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]:
            return False
        if not isinstance(event.caller, AVGECharacterCard):
            return False
        if event.caller.player != self.owner_card.player.opponent:
            return False
        # Attach only when incoming attack is potentially large enough.
        return event.magnitude >= 60

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        if self.owner_card.cardholder is None or self.owner_card.cardholder.pile_type not in [Pile.BENCH, Pile.ACTIVE]:
            self.invalidate()

    def react(self, args=None):
        if args is None:
            args = {}

        event = self.attached_event
        assert isinstance(event, AVGECardHPChange)
        assert isinstance(event.caller, AVGECharacterCard)

        if not isinstance(event.old_amt, int) or not isinstance(event.final_change, int):
            return Response(ResponseType.ACCEPT, Data())

        hp_lost = max(0, event.old_amt - event.final_change)
        if hp_lost < 60:
            return Response(ResponseType.ACCEPT, Data())

        self.propose(
            AVGEPacket([
                AVGECardHPChange(
                    event.caller,
                    hp_lost,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.PASSIVE,
                    None,
                    self.owner_card,
                )
            ], AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, WestonPoe))
        )
        return Response(ResponseType.ACCEPT, Notify('Weston Poe: Right Back At You! Reflected damage equal to HP lost.', all_players, default_timeout))
    
    def __str__(self):
        return "Weston Poe: Right Back At You!"


class WestonPoe(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.WOODWIND, 2, 2)
        self.has_passive = True
        self.atk_1_name = 'Overblow'

    def passive(self) -> Response:
        self.add_listener(_WestonRightBackAtYouReactor(self))
        return Response(ResponseType.CORE, Data())

    def atk_1(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:

        def gen() -> PacketType:
            packet: PacketType = []
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        50,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.WOODWIND,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )
            packet.append(
                AVGECardHPChange(
                    card,
                    10,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_1,
                    None,
                    card,
                )
            )
            return packet

        card.propose(
            AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_1, WestonPoe))
        )
        return self.generic_response(card, ActionTypes.ATK_1)
