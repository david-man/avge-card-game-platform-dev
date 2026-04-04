from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import *



class _JuanBenchAttackBoost(AVGEModifier):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=(owner_card, AVGEEventListenerType.PASSIVE), group=EngineGroup.EXTERNAL_MODIFIERS_2)
        self.owner_card = owner_card

    def event_match(self, event):
        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if not isinstance(event.caller_card, AVGECharacterCard):
            return False
        if event.caller_card.player != self.owner_card.player:
            return False
        if self.owner_card.cardholder.pile_type != Pile.BENCH:
            return False
        if event.caller_card.cardholder.pile_type != Pile.ACTIVE:
            return False
        if event.caller_card.card_type != CardType.BRASS:
            return False
        return True

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return True

    def package(self):
        return "JuanBurgos Bench Attack Boost"

    def modify(self, args=None):
        event : AVGECardHPChange = self.attached_event
        # add +20 damage to the attack
        event.modify_magnitude(20)
        return self.generate_response()


class JuanBurgos(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.BRASS, 1, 3)
        self.has_atk_1 = True
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False
    @staticmethod
    def passive(card : AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        # attach bench boost modifier globally while in play
        card.add_listener(_JuanBenchAttackBoost(card))
        return card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import AVGECardHPChange
        opponent = card.player.opponent
        def generate_packet():
        # count brass characters on your bench
            bench = card.player.cardholders[ Pile.BENCH ]
            brass_count = 0
            c : AVGECharacterCard
            for c in bench:
                if c.card_type == CardType.BRASS:
                    brass_count += 1

            extra = 20 * brass_count
            damage = 40 + extra

            return [AVGECardHPChange(
                    lambda : opponent.get_active_card(),
                    damage,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    ActionTypes.ATK_1,
                    CardType.BRASS,
                    card,
                )]
        card.propose(generate_packet)

        return card.generate_response()
