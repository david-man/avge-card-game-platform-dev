from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEConstrainer import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class DemiLuDamageBlockModifier(AVGEAssessor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=(owner_card, AVGEEventListenerType.PASSIVE), group=EngineGroup.EXTERNAL_PRECHECK_1)
        self.owner_card = owner_card

    def event_match(self, event):
        from card_game.internal_events import AVGECardHPChange
        from card_game.catalog.stadiums.SteinertBasement import SteinertBasement
        from card_game.catalog.stadiums.SteinertPracticeRoom import SteinertPracticeRoom

        if not isinstance(event, AVGECardHPChange):
            return False
        if event.target_card != self.owner_card:
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if self.owner_card.cardholder.pile_type != Pile.BENCH:
            return False
        if len(self.owner_card.env.stadium_cardholder) == 0:
            return False
        if event.change_type == CardType.ALL:
            return False
        stadium = self.owner_card.env.stadium_cardholder.peek()
        return isinstance(stadium, (SteinertBasement, SteinertPracticeRoom))

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return True

    def package(self):
        return "DemiLu Damage Immunity Modifier"

    def assess(self, args=None):
        if args is None:
            args = {}
        return self.generate_response(ResponseType.FAST_FORWARD)


class DemiLuConstraint(AVGEConstraint):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__((owner_card, AVGEConstrainerType.PASSIVE))
        self.owner_card = owner_card

    def match(self, obj: AVGEAbstractEventListener | AVGEConstraint):
        from card_game.catalog.stadiums.SteinertPracticeRoom import SteinertPracticeRoomAttackExtraCostAssessor
        from card_game.catalog.stadiums.SteinertBasement import SteinertBasementAttackExtraCostAssessor

        if not isinstance(obj, (SteinertPracticeRoomAttackExtraCostAssessor, SteinertBasementAttackExtraCostAssessor)):
            return False
        event = obj.attached_event
        return event.card == self.owner_card

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return True

    def package(self):
        return "DemiLu Constraint"


class DemiLu(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.PIANO, 1, 1, 2)
        self.has_atk_1 = True
        self.atk_1_cost = 1
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        card.add_listener(DemiLuDamageBlockModifier(card))
        card.add_constrainer(DemiLuConstraint(card))
        return card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import AVGECardHPChange

        bench_cards = [c for c in card.player.cardholders[Pile.BENCH] if c != card]
        found_piano = any(c.card_type == CardType.PIANO for c in bench_cards)
        dmg = 80 if found_piano else 50

        card.propose(
            AVGECardHPChange(
                lambda: card.player.opponent.get_active_card(),
                dmg,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.PIANO,
                ActionTypes.ATK_1,
                card,
            )
        )

        return card.generate_response()
