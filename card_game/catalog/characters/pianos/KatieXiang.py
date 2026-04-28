from __future__ import annotations

from card_game.avge_abstracts import *

from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import AVGECardHPChange


class KatieTurnEndReactor(AVGEReactor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, KatieXiang), group=EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card

    def event_match(self, event):
        from card_game.internal_events import TurnEnd

        if not isinstance(event, TurnEnd):
            return False
        if self.owner_card.cardholder is None or self.owner_card.cardholder.pile_type not in [Pile.ACTIVE, Pile.BENCH]:
            return False
        return event.env.player_turn == self.owner_card.player.opponent and self.owner_card.hp < 50

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return
    
    def react(self, args=None):
        if args is None:
            args = {}

        owner = self.owner_card

        def generate_packet() -> PacketType:
            packet: PacketType = []
            for c in owner.player.get_cards_in_play():
                if isinstance(c, AVGECharacterCard):
                    packet.append(
                        AVGECardHPChange(
                            c,
                            20,
                            AVGEAttributeModifier.ADDITIVE,
                            CardType.ALL,
                            ActionTypes.PASSIVE,
                            None,
                            owner,
                        )
                    )
            return packet

        self.propose(AVGEPacket([generate_packet], AVGEEngineID(owner, ActionTypes.PASSIVE, KatieXiang)), 1)
        return Response(ResponseType.ACCEPT, Data())


class _KatieRubatoDelayedReactor(AVGEReactor):
    def __init__(self, owner_card: AVGECharacterCard, trigger_round: int):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.ATK_1, KatieXiang), group=EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card
        self.trigger_round = trigger_round

    def event_match(self, event):
        from card_game.internal_events import TurnEnd

        return (
            isinstance(event, TurnEnd)
            and self.owner_card.env.round_id == self.trigger_round
            and self.owner_card.env.player_turn == self.owner_card.player
        )

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        if self.owner_card.env.round_id > self.trigger_round:
            self.invalidate()

    def react(self, args=None):
        if args is None:
            args = {}

        owner = self.owner_card

        def generate_packet() -> PacketType:
            packet: PacketType = []
            active = owner.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        30,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.PIANO,
                        ActionTypes.PASSIVE,
                        None,
                        owner,
                    )
                )
            return packet

        owner.propose(AVGEPacket([generate_packet], AVGEEngineID(owner, ActionTypes.PASSIVE, KatieXiang)), 1)
        self.invalidate()
        return Response(ResponseType.ACCEPT, Data())


class KatieXiang(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.PIANO, 2, 2)
        self.atk_1_name = 'Rubato'
        self.has_passive = True

    def passive(self) -> Response:
        self.add_listener(KatieTurnEndReactor(self))
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
            ], AVGEEngineID(card, ActionTypes.ATK_1, KatieXiang))
        )

        trigger_round = card.player.get_next_turn()
        card.env.add_listener(_KatieRubatoDelayedReactor(card, trigger_round))

        return self.generic_response(card, ActionTypes.ATK_1)
