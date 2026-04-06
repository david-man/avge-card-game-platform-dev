from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import AVGEModifier
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class FelixChen(AVGECharacterCard):
    _COIN_KEY_0 = "felixchen_coin_0"
    _COIN_KEY_1 = "felixchen_coin_1"

    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.WOODWIND, 1, 3)
        self.has_atk_1 = True
        self.atk_1_cost = 3
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard) -> Response:
        owner_card = card

        class _FelixDamageReducer(AVGEModifier):
            def __init__(self):
                super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, FelixChen), group=EngineGroup.EXTERNAL_MODIFIERS_2)

            def event_match(self, event):
                from card_game.internal_events import AVGECardHPChange

                if not isinstance(event, AVGECardHPChange):
                    return False
                if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                    return False
                if event.target_card.player != owner_card.player:
                    return False
                types = [c.card_type for c in owner_card.player.get_cards_in_play()]
                return len(types) == len(set(types))

            def event_effect(self) -> bool:
                return True

            def update_status(self):
                return

            def make_announcement(self) -> bool:
                return True

            def package(self):
                return "FelixChen Damage Reducer"

            def modify(self, args=None):
                if args is None:
                    args = {}
                from card_game.internal_events import AVGECardHPChange

                event = self.attached_event
                assert isinstance(event, AVGECardHPChange)
                event.modify_magnitude(-10)
                return self.generate_response()

        owner_card.add_listener(_FelixDamageReducer())
        return owner_card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange, InputEvent

        opponent = card.player.opponent
        bench = opponent.cardholders[Pile.BENCH]
        if len(bench) == 0:
            return card.generate_response()

        roll0 = card.env.cache.get(card, FelixChen._COIN_KEY_0, None, True)
        roll1 = card.env.cache.get(card, FelixChen._COIN_KEY_1, None, True)
        if roll0 is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [FelixChen._COIN_KEY_0, FelixChen._COIN_KEY_1],
                            InputType.COIN,
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            {"query_label": "felixchen_multiphonics"},
                        )
                    ]
                },
            )

        if roll0 == 1 and roll1 == 1:
            dmg = 50
        elif roll0 == 0 and roll1 == 0:
            dmg = 100
        else:
            return card.generate_response()
        

        packet = [
            AVGECardHPChange(
                target,
                dmg,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.WOODWIND,
                ActionTypes.ATK_1,
                card,
            )
            for target in opponent.cardholders[Pile.BENCH] if isinstance(target, AVGECharacterCard)
        ]
        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, FelixChen)))
        return card.generate_response()
