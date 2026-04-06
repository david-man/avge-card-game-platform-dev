from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import AVGEModifier
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class AshleyToby(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.STRING, 1, 2)
        self.has_atk_1 = True
        self.atk_1_cost = 2
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard) -> Response:
        owner_card = card

        class _BothBenchesFullAttackModifier(AVGEModifier):
            def __init__(self):
                super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, AshleyToby), group=EngineGroup.EXTERNAL_MODIFIERS_2)

            def event_match(self, event):
                from card_game.internal_events import AVGECardHPChange

                if not isinstance(event, AVGECardHPChange):
                    return False
                if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                    return False
                if event.caller_card != owner_card:
                    return False
                if owner_card.player is None or owner_card.player.opponent is None:
                    return False
                my_bench = owner_card.player.cardholders[Pile.BENCH]
                opp_bench = owner_card.player.opponent.cardholders[Pile.BENCH]
                return len(my_bench) == max_bench_size and len(opp_bench) == max_bench_size

            def event_effect(self) -> bool:
                return True

            def update_status(self):
                return

            def make_announcement(self) -> bool:
                return True

            def package(self):
                return "AshleyToby Double Damage Modifier"

            def modify(self, args=None):
                if args is None:
                    args = {}
                from card_game.internal_events import AVGECardHPChange

                event = self.attached_event
                assert isinstance(event, AVGECardHPChange)
                event.modify_magnitude(event.magnitude)
                return self.generate_response()

        owner_card.add_listener(_BothBenchesFullAttackModifier())
        return owner_card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChangeCreator

        card.propose(
            AVGEPacket([
                AVGECardHPChangeCreator(
                    lambda: card.player.opponent.get_active_card(),
                    40,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.STRING,
                    ActionTypes.ATK_1,
                    card,
                )
            ], AVGEEngineID(card, ActionTypes.ATK_1, AshleyToby))
        )
        return card.generate_response()
