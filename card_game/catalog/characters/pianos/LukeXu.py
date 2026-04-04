from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEConstrainer import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *
from card_game.engine.engine_constants import *
import math


class LukeXuPassiveConstraint(AVGEConstraint):
    def __init__(self, owner_card: AVGECharacterCard, round_played: int):
        super().__init__((owner_card, AVGEConstrainerType.PASSIVE))
        self.owner_card = owner_card
        self.round_played = round_played

    def match(self, obj: AVGEAbstractEventListener | AVGEConstraint):
        from card_game.avge_abstracts.AVGEEventListeners import AVGEEventListenerType

        listener_id = obj.identifier
        if listener_id[1] != AVGEEventListenerType.PASSIVE:
            return False
        listener_owner = listener_id[0]
        return isinstance(listener_owner, AVGECharacterCard) and listener_owner.player == self.owner_card.player.opponent

    def update_status(self):
        if self.owner_card.env.round_id != self.round_played:
            self.invalidate()

    def make_announcement(self) -> bool:
        return True

    def package(self):
        return "LukeXu Passive Constraint"


class LukeNextAttackHalvedModifier(AVGEModifier):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=(owner_card, AVGEEventListenerType.NONCHAR), group=EngineGroup.EXTERNAL_MODIFIERS_2)
        self.owner_card = owner_card

    def event_match(self, event):
        from card_game.internal_events import AVGECardHPChange

        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]:
            return False
        if(event.caller_card is None):
            return False
        return event.caller_card.player == self.owner_card.player.opponent

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return True

    def package(self):
        return "LukeXu Next Attack Halved Modifier"

    def on_packet_completion(self):
        self.invalidate()

    def modify(self, args=None):
        if args is None:
            args = {}
        event = self.attached_event
        event.modify_magnitude(-math.floor(event.magnitude / 2))
        return self.generate_response()


class LukeXu(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.PIANO, 1, 1)
        self.has_atk_1 = True
        self.atk_1_cost = 1
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        card.add_constrainer(LukeXuPassiveConstraint(card, card.env.round_id))
        return card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import AVGECardHPChange

        card.propose(
            AVGECardHPChange(
                lambda: card.player.opponent.get_active_card(),
                20,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.PIANO,
                ActionTypes.ATK_1,
                card,
            )
        )

        card.add_listener(LukeNextAttackHalvedModifier(card))

        return card.generate_response()
