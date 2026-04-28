from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import AVGECardHPChange


class _AshleyBothBenchesFullAttackModifier(AVGEModifier):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, AshleyToby), group=EngineGroup.EXTERNAL_MODIFIERS_2)
        self.owner_card = owner_card

    def event_match(self, event):
        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if event.caller != self.owner_card:
            return False
        if self.owner_card.cardholder is None or self.owner_card.cardholder.pile_type not in [Pile.ACTIVE, Pile.BENCH]:
            return False
        if self.owner_card.player is None or self.owner_card.player.opponent is None:
            return False

        my_bench = self.owner_card.player.cardholders[Pile.BENCH]
        opp_bench = self.owner_card.player.opponent.cardholders[Pile.BENCH]
        return len(my_bench) == max_bench_size and len(opp_bench) == max_bench_size

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def modify(self, args=None):
        if args is None:
            args = {}

        event = self.attached_event
        assert isinstance(event, AVGECardHPChange)
        event.modify_magnitude(event.magnitude)
        return Response(ResponseType.ACCEPT, Notify('Instagram Viral: Ashley Toby doubled her damage because both benches are full.', all_players, default_timeout))


class AshleyToby(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 1, 2)
        self.atk_1_name = 'Code Gyu: Seal Attack'
        self.has_passive = True

    def passive(self) -> Response:
        self.add_listener(_AshleyBothBenchesFullAttackModifier(self))
        return Response(ResponseType.CORE, Data())

    def atk_1(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        def generate_packet() -> PacketType:
            active = card.player.opponent.get_active_card()
            packet: PacketType = []
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        40,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.STRING,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )
            return packet

        card.propose(
            AVGEPacket([
                generate_packet
            ], AVGEEngineID(card, ActionTypes.ATK_1, AshleyToby))
        )
        return self.generic_response(card, ActionTypes.ATK_1)
