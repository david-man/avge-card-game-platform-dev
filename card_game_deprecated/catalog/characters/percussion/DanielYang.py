from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from typing import cast

class _NoBrassBoostModifier(AVGEModifier):
    def __init__(self, owner_card : AVGECharacterCard):
        super().__init__(
            identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, DanielYang),
            group=EngineGroup.EXTERNAL_MODIFIERS_2,
        )
        self.owner_card = owner_card

    def event_match(self, event):
        from card_game.internal_events import AVGECardHPChange

        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if event.change_type == CardType.ALL:
            return False
        if event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]:
            return False
        if event.caller != self.owner_card:
            return False
        env = self.owner_card.env
        for p in env.players.values():
            for c in p.get_cards_in_play():
                if c.card_type == CardType.BRASS:
                    return False

        return True

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def modify(self):
        from card_game.internal_events import AVGECardHPChange

        event = self.attached_event
        assert isinstance(event, AVGECardHPChange)
        event.modify_magnitude(10)
        return Response(ResponseType.ACCEPT, Notify('Delicate Ears: +10 damage', all_players, default_timeout))
    
    def __str__(self):
        return "Daniel Yang: Delicate Ears Buff"
class DanielYang(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.PIANO, 2, 3)
        self.atk_1_name = 'Eight Hands Piano'
        self.has_passive = True

    def passive(self) -> Response:
        owner_card = self
        self.add_listener(_NoBrassBoostModifier(owner_card))
        return Response(ResponseType.CORE, Data())

    def atk_1(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        from card_game.internal_events import AVGECardHPChange

        bench = card.player.cardholders[Pile.BENCH]
        piano_count = sum(1 for c in bench if isinstance(c, AVGECharacterCard) and c.card_type == CardType.PIANO)

        def generate_packet() -> PacketType:
            packet: PacketType = []
            packet.append(
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    50,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PIANO,
                    ActionTypes.ATK_1,
                    None,
                    card,
                )
            )
            if piano_count >= 3:
                for b in card.player.opponent.cardholders[Pile.BENCH]:
                    packet.append(
                        AVGECardHPChange(
                            cast(AVGECharacterCard, b),
                            30,
                            AVGEAttributeModifier.SUBSTRACTIVE,
                            CardType.PIANO,
                            ActionTypes.ATK_1,
                            None,
                            card,
                        )
                    )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, DanielYang)))
        return self.generic_response(card, ActionTypes.ATK_1)
