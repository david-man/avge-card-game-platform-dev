from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import AVGEReactor
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class WestonPoe(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.WOODWIND, 2, 2)
        self.has_atk_1 = True
        self.atk_1_cost = 2
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard) -> Response:
        owner_card = card

        class _DamageReflector(AVGEReactor):
            def __init__(self):
                super().__init__(
                    identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, WestonPoe),
                    group=EngineGroup.EXTERNAL_REACTORS,
                )

            def event_match(self, event):
                from card_game.internal_events import AVGECardHPChange

                if not isinstance(event, AVGECardHPChange):
                    return False
                if event.target_card != owner_card:
                    return False
                if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                    return False
                if event.magnitude < 60:
                    return False
                if event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]:
                    return False
                if not isinstance(event.caller_card, AVGECharacterCard):
                    return False
                if event.caller_card.player != owner_card.player.opponent:
                    return False
                return True

            def event_effect(self) -> bool:
                return True

            def update_status(self):
                if owner_card.env is None:
                    self.invalidate()

            def make_announcement(self) -> bool:
                return True

            def package(self):
                return "WestonPoe Passive Reactor"

            def react(self, args=None):
                if args is None:
                    args = {}
                from card_game.internal_events import AVGECardHPChange

                event = self.attached_event
                assert isinstance(event, AVGECardHPChange)
                assert isinstance(event.caller_card, AVGECharacterCard)
                self.propose(
                    AVGEPacket([
                        AVGECardHPChange(
                            event.caller_card,
                            event.magnitude,
                            AVGEAttributeModifier.SUBSTRACTIVE,
                            CardType.WOODWIND,
                            ActionTypes.PASSIVE,
                            owner_card,
                        )
                    ], AVGEEngineID(owner_card, ActionTypes.PASSIVE, WestonPoe))
                )
                return self.generate_response()

        owner_card.add_listener(_DamageReflector())
        return owner_card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        card.propose(
            AVGEPacket([
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    50,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_1,
                    card,
                ),
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    10,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_1,
                    card,
                ),
            ], AVGEEngineID(card, ActionTypes.ATK_1, WestonPoe))
        )
        return card.generate_response()
