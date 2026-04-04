from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class JordanRoosevelt(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.WOODWIND, 1, 1, 2)
        self.has_atk_1 = True
        self.atk_1_cost = 1
        self.has_atk_2 = True
        self.atk_2_cost = 2
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        next_opp_round = card.player.opponent.get_next_turn()
        next_player_round = card.player.get_next_turn()

        class _OpponentAttackBuff(AVGEModifier):
            def __init__(self):
                super().__init__(identifier=(card, AVGEEventListenerType.ATK_1), group=EngineGroup.EXTERNAL_MODIFIERS_2)

            def event_match(self, event):
                from card_game.internal_events import AVGECardHPChange

                if not isinstance(event, AVGECardHPChange):
                    return False
                if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                    return False
                if event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]:
                    return False
                if not isinstance(event.caller_card, AVGECharacterCard):
                    return False
                return event.caller_card.player == card.player.opponent and card.env.round_id == next_opp_round

            def event_effect(self) -> bool:
                return True

            def update_status(self):
                if card.env.round_id > next_opp_round:
                    self.invalidate()

            def make_announcement(self) -> bool:
                return False

            def package(self):
                return "JordanRoosevelt Opponent Attack Buff"

            def modify(self, args=None):
                if args is None:
                    args = {}
                self.attached_event.modify_magnitude(20)
                return self.generate_response()

        class _JordanAttackBuff(AVGEModifier):
            def __init__(self):
                super().__init__(identifier=(card, AVGEEventListenerType.ATK_1), group=EngineGroup.EXTERNAL_MODIFIERS_2)

            def event_match(self, event):
                from card_game.internal_events import AVGECardHPChange

                if not isinstance(event, AVGECardHPChange):
                    return False
                if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                    return False
                if event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]:
                    return False
                return event.caller_card == card

            def event_effect(self) -> bool:
                return True

            def update_status(self):
                if card.env.round_id > next_player_round:
                    self.invalidate()

            def make_announcement(self) -> bool:
                return False

            def package(self):
                return "JordanRoosevelt Self Attack Buff"

            def modify(self, args=None):
                if args is None:
                    args = {}
                self.attached_event.modify_magnitude(60)
                return self.generate_response()

        card.add_listener(_OpponentAttackBuff())
        card.add_listener(_JordanAttackBuff())
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import AVGECardHPChange

        card.propose(
            [
                AVGECardHPChange(
                    lambda: card.player.opponent.get_active_card(),
                    30,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_2,
                    card,
                ),
                AVGECardHPChange(
                    card,
                    20,
                    AVGEAttributeModifier.ADDITIVE,
                    card.card_type,
                    ActionTypes.ATK_2,
                    card,
                ),
            ]
        )
        return card.generate_response()
