from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import AVGECardHPChange, AVGEEnergyTransfer, TransferCard
import math


class SophiaNextAttackHalvedModifier(AVGEModifier):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.NONCHAR, SophiaSWang), group=EngineGroup.EXTERNAL_MODIFIERS_2)
        self.owner_card = owner_card

    def event_match(self, event):
        from card_game.internal_events import AVGECardHPChange

        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]:
            return False
        if(not isinstance(event.caller, AVGECharacterCard)):
            return False
        if event.change_type == CardType.ALL:
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


class _SophiaEnergyReactor(AVGEReactor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, SophiaSWang), group=EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card

    def event_match(self, event):
        if not isinstance(event, AVGEEnergyTransfer):
            return False
        if event.target != self.owner_card:
            return False
        if self.owner_card.cardholder is None or self.owner_card.cardholder.pile_type not in [Pile.ACTIVE, Pile.BENCH]:
            return False
        _, already_triggered_idx = self.owner_card.env.check_history(
            self.owner_card.env.round_id,
            AVGEEnergyTransfer,
            {
                'target': self.owner_card,
            },
        )
        deck = self.owner_card.player.opponent.cardholders[Pile.DECK]
        if already_triggered_idx != -1:
            return False
        return len(deck) > 0

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return


    def react(self, args=None):
        if args is None:
            args = {}

        owner = self.owner_card

        opp = owner.player.opponent
        deck = opp.cardholders[Pile.DECK]
        discard = opp.cardholders[Pile.DISCARD]

        def mill_top() -> PacketType:
            packet: PacketType = []
            if len(deck) == 0:
                return packet
            packet.append(
                TransferCard(
                    deck.peek(),
                    deck,
                    discard,
                    ActionTypes.PASSIVE,
                    owner,
                    None,
                )
            )
            return packet

        owner.propose(
            AVGEPacket([
                mill_top
            ], AVGEEngineID(owner, ActionTypes.PASSIVE, SophiaSWang))
        )
        return Response(ResponseType.ACCEPT, Notify('The Original is Always Better: Opponent discards the top card of their deck.', all_players, default_timeout))


class SophiaSWang(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.PIANO, 2, 2)
        self.atk_1_name = 'Damper Pedal'
        self.has_passive = True

    def passive(self) -> Response:
        self.add_listener(_SophiaEnergyReactor(self))
        return Response(ResponseType.CORE, Data())

    def atk_1(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        def generate_packet() -> PacketType:
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
            AVGEPacket([
                generate_packet
            ], AVGEEngineID(card, ActionTypes.ATK_1, SophiaSWang))
        )

        card.add_listener(SophiaNextAttackHalvedModifier(card))

        return self.generic_response(card, ActionTypes.ATK_1)
