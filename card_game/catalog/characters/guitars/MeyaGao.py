from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import AVGEModifier, AVGEAssessor, AVGEReactor
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class _MeyaGuitarBoost(AVGEModifier):
    def __init__(self, owner_card: AVGECharacterCard, round_active: int):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.NONCHAR, MeyaGao), group=EngineGroup.EXTERNAL_MODIFIERS_2)
        self.owner_card = owner_card
        self.round_active = round_active

    def event_match(self, event):
        from card_game.internal_events import AVGECardHPChange

        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if not isinstance(event.caller_card, AVGECharacterCard):
            return False
        if event.caller_card.player != self.owner_card.player:
            return False
        if event.change_type != CardType.GUITAR:
            return False
        if self.owner_card.env.round_id != self.round_active:
            return False
        return True

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        if self.owner_card.env.round_id > self.round_active:
            self.invalidate()

    def make_announcement(self) -> bool:
        return True

    def package(self):
        return "MeyaGao Guitar Boost Modifier"

    def modify(self, args=None):
        if args is None:
            args = {}
        from card_game.internal_events import AVGECardHPChange

        event = self.attached_event
        assert isinstance(event, AVGECardHPChange)
        event.modify_magnitude(40)
        return self.generate_response()


class _MeyaAttackBlockAssessor(AVGEAssessor):
    def __init__(self, owner_card: AVGECharacterCard, round_active: int):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, MeyaGao), group=EngineGroup.EXTERNAL_PRECHECK_1)
        self.card_blocked = owner_card
        self.round_active = round_active

    def event_match(self, event):
        from card_game.internal_events import PlayCharacterCard

        if not isinstance(event, PlayCharacterCard):
            return False
        if event.card_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]:
            return False
        if not isinstance(event.card, AVGECharacterCard):
            return False
        if event.caller_card != self.card_blocked:
            return False
        if self.card_blocked.env.round_id != self.round_active:
            return False
        return True

    def update_status(self):
        if self.card_blocked.env.round_id > self.round_active:
            self.invalidate()

    def make_announcement(self) -> bool:
        return True

    def package(self):
        return "MeyaGao Attack Block Assessor"

    def assess(self, args=None) -> Response:
        if args is None:
            args = {}
        return self.generate_response(ResponseType.SKIP, {"msg": "Cannot attack this round due to MeyaGao passive"})


class _MeyaDamageReactor(AVGEReactor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, MeyaGao), group=EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card

    def event_match(self, event):
        from card_game.internal_events import AVGECardHPChange

        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        return event.target_card == self.owner_card and isinstance(event.caller_card, AVGECharacterCard)

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return True

    def package(self):
        return "MeyaGao Damage Reactor"

    def react(self, args=None) -> Response:
        if args is None:
            args = {}
        from card_game.internal_events import AVGECardHPChange

        event = self.attached_event
        assert isinstance(event, AVGECardHPChange)
        assert isinstance(event.caller_card, AVGECharacterCard)
        attacker: AVGECharacterCard = event.caller_card

        self.owner_card.add_listener(_MeyaAttackBlockAssessor(self.owner_card, self.owner_card.player.get_next_turn()))
        attacker.add_listener(_MeyaAttackBlockAssessor(attacker, attacker.player.get_next_turn()))

        return self.generate_response()


class MeyaGao(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 120, CardType.GUITAR, 2, 2, 0)
        self.has_atk_1 = False
        self.has_atk_2 = True
        self.atk_2_cost = 0
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard) -> Response:
        card.add_listener(_MeyaDamageReactor(card))
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChangeCreator

        card.propose(
            AVGEPacket([
                AVGECardHPChangeCreator(
                    lambda: card.player.opponent.get_active_card(),
                    40,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.GUITAR,
                    ActionTypes.ATK_2,
                    card,
                )
            ], AVGEEngineID(card, ActionTypes.ATK_2, MeyaGao))
        )
        card.add_listener(_MeyaGuitarBoost(card, card.player.get_next_turn()))

        return card.generate_response()
