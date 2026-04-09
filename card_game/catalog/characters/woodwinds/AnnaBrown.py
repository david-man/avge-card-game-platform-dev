from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class AnnaBrown(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.WOODWIND, 2, 0, 2)
        self.has_atk_1 = False
        self.has_atk_2 = True
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard) -> Response:
        owner_card = card

        class _BenchDamageReducer(AVGEModifier):
            def __init__(self):
                super().__init__(
                    identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, AnnaBrown),
                    group=EngineGroup.EXTERNAL_MODIFIERS_2,
                )

            def event_match(self, event):
                from card_game.internal_events import AVGECardHPChange

                if not isinstance(event, AVGECardHPChange):
                    return False
                if event.target_card != owner_card:
                    return False
                if owner_card.cardholder is None or owner_card.cardholder.pile_type != Pile.BENCH:
                    return False
                if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                    return False
                return True

            def event_effect(self) -> bool:
                return True

            def update_status(self):
                if owner_card.env is None:
                    self.invalidate()


            def modify(self, args=None):
                if args is None:
                    args = {}
                from card_game.internal_events import AVGECardHPChange

                event = self.attached_event
                assert isinstance(event, AVGECardHPChange)
                event.modify_magnitude(-20)
                return self.generate_response()

        owner_card.add_listener(_BenchDamageReducer())
        return owner_card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange
        def gen() -> PacketType:
            return [
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    50,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_2,
                    card,
                ),
                AVGECardHPChange(
                    card,
                    10,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_2,
                    card,
                ),
            ]
        card.propose(
            AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_2, AnnaBrown))
        )
        return card.generate_response()
