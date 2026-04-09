from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from typing import cast


class DanielYang(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.PERCUSSION, 2, 3)
        self.has_atk_1 = True
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard) -> Response:
        owner_card = card

        class _NoBrassBoostModifier(AVGEModifier):
            def __init__(self):
                super().__init__(
                    identifier=AVGEEngineID(card, ActionTypes.PASSIVE, DanielYang),
                    group=EngineGroup.EXTERNAL_MODIFIERS_2,
                )

            def event_match(self, event):
                from card_game.internal_events import AVGECardHPChange

                if not isinstance(event, AVGECardHPChange):
                    return False
                if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                    return False
                
                if event.caller_card != owner_card:
                    return False

                env = owner_card.env
                for p in env.players.values():
                    for c in p.get_cards_in_play():
                        if c.card_type == CardType.BRASS:
                            return False

                return True

            def event_effect(self) -> bool:
                return True

            def update_status(self):
                return

            def modify(self, args=None):
                if args is None:
                    args = {}
                from card_game.internal_events import AVGECardHPChange

                event = self.attached_event
                assert isinstance(event, AVGECardHPChange)
                event.modify_magnitude(20)
                return self.generate_response()

        card.add_listener(_NoBrassBoostModifier())
        return owner_card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        bench = card.player.cardholders[Pile.BENCH]
        piano_count = sum(1 for c in bench if isinstance(c, AVGECharacterCard) and c.card_type == CardType.PIANO)

        def generate_packet():
            packet = []
            packet.append([
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    50,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PERCUSSION,
                    ActionTypes.ATK_1,
                    card,
                )
            ])
            if piano_count >= 3:
                for b in card.player.opponent.cardholders[Pile.BENCH]:
                    packet.append(
                        AVGECardHPChange(
                            cast(AVGECharacterCard, b),
                            30,
                            AVGEAttributeModifier.SUBSTRACTIVE,
                            CardType.PERCUSSION,
                            ActionTypes.ATK_1,
                            card,
                        )
                    )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, DanielYang)))
        return card.generate_response()
