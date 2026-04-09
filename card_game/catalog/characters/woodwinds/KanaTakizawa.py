from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class KanaTakizawa(AVGECharacterCard):
    _D6_ROLL_KEY = "kanatakizawa_d6_roll"

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.WOODWIND, 2, 3)
        self.has_atk_1 = True
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard) -> Response:
        owner_card = card

        class _DamageReducer(AVGEModifier):
            def __init__(self):
                super().__init__(
                    identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, KanaTakizawa),
                    group=EngineGroup.EXTERNAL_MODIFIERS_3,
                )

            def event_match(self, event):
                from card_game.internal_events import AVGECardHPChange

                if not isinstance(event, AVGECardHPChange):
                    return False
                if event.target_card != owner_card:
                    return False
                if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                    return False
                return True

            def event_effect(self) -> bool:
                return True

            def update_status(self):
                return

            def make_announcement(self) -> bool:
                return True

            def package(self):
                return "KanaTakizawa Damage Reducer"

            def modify(self, args=None):
                if args is None:
                    args = {}
                from card_game.internal_events import AVGECardHPChange

                event = self.attached_event
                assert isinstance(event, AVGECardHPChange)
                event.modify_magnitude(-10)
                return self.generate_response()

        owner_card.add_listener(_DamageReducer())
        return owner_card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange, InputEvent

        roll = card.env.cache.get(card, KanaTakizawa._D6_ROLL_KEY, None, True)
        if roll is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [KanaTakizawa._D6_ROLL_KEY],
                            InputType.D6,
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            {"query_label": "kana_d6"},
                        )
                    ]
                },
            )

        damage = 30 + 10 * int(roll)
        def generate_packet() -> PacketType:
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                return [
                    AVGECardHPChange(
                        active,
                        damage,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.WOODWIND,
                        ActionTypes.ATK_1,
                        card,
                    )
                ]
            return []

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, KanaTakizawa)))
        return card.generate_response()
