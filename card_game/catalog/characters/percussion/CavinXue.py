from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class CavinMaidBoostModifier(AVGEModifier):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=(owner_card, AVGEEventListenerType.NONCHAR), group=EngineGroup.EXTERNAL_MODIFIERS_2)
        self.owner_card = owner_card

    def event_match(self, event):
        from card_game.internal_events import AVGECardHPChange

        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        
        if event.caller_card != self.owner_card:
            return False

        env = self.owner_card.env
        maid_count = 0
        for player in env.players.values():
            for c in player.get_cards_in_play():
                if len(c.statuses_attached[StatusEffect.MAID]) > 0:
                    maid_count += 1

        return maid_count > 0

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        if self.owner_card.env is None or self.owner_card.cardholder is None:
            self.invalidate()
            return
        if self.owner_card.cardholder.pile_type != Pile.ACTIVE:
            self.invalidate()

    def make_announcement(self) -> bool:
        return True

    def package(self):
        return "CavinXue Maid Boost Modifier"

    def modify(self, args=None):
        if args is None:
            args = {}
        event = self.attached_event

        env = self.owner_card.env
        maid_count = 0
        for player in env.players.values():
            for c in player.get_cards_in_play():
                if len(c.statuses_attached[StatusEffect.MAID]) > 0:
                    maid_count += 1

        event.modify_magnitude(20 * maid_count)
        return self.generate_response()


class CavinXue(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.PERCUSSION, 1, 1)
        self.has_atk_1 = True
        self.atk_1_cost = 1
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        card.add_listener(CavinMaidBoostModifier(card))
        return card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import AVGECardHPChange

        card.propose(
            AVGECardHPChange(
                lambda: card.player.opponent.get_active_card(),
                20,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.PERCUSSION,
                ActionTypes.ATK_1,
                card,
            )
        )

        return card.generate_response()
