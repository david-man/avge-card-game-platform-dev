from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import AVGEModifier
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class RyanLiMaidDamageModifier(AVGEModifier):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.NONCHAR, RyanLi), group=EngineGroup.EXTERNAL_MODIFIERS_2)
        self.owner_card = owner_card

    def event_match(self, event):
        from card_game.internal_events import AVGECardHPChange

        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if not isinstance(event.caller_card, AVGECharacterCard):
            return False

        caller = event.caller_card
        return len(caller.statuses_attached[StatusEffect.MAID]) > 0

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return True

    def package(self):
        return "RyanLi Maid Damage Modifier"

    def modify(self, args=None):
        if args is None:
            args = {}
        from card_game.internal_events import AVGECardHPChange

        event = self.attached_event
        assert isinstance(event, AVGECardHPChange)
        event.modify_magnitude(-10)
        return self.generate_response()


class RyanLi(AVGECharacterCard):
    _LAST_ATK1_ROUND_KEY = "ryanli_atk1_last_round"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.PIANO, 1, 1, 2)
        self.has_atk_1 = True
        self.atk_1_cost = 1
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard) -> Response:
        card.add_listener(RyanLiMaidDamageModifier(card))
        return card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChangeCreator

        last_round = card.env.cache.get(card, RyanLi._LAST_ATK1_ROUND_KEY, None, True)
        if last_round is None or last_round < card.env.round_id - 1:
            card.propose(
                AVGEPacket([
                    AVGECardHPChangeCreator(
                        lambda: card.player.opponent.get_active_card(),
                        40,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.PIANO,
                        ActionTypes.ATK_1,
                        card,
                    )
                ], AVGEEngineID(card, ActionTypes.ATK_1, RyanLi))
            )

        card.env.cache.set(card, RyanLi._LAST_ATK1_ROUND_KEY, card.env.round_id)
        return card.generate_response()
