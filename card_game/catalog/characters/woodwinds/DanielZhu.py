from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class DanielZhu(AVGECharacterCard):
    _D6_ROLL_KEY = "danielzhu_d6_roll"
    _REDIRECT_KEY = "danielzhu_damage_redirect"

    def __init__(self, unique_id):
        super().__init__(unique_id, 120, CardType.WOODWIND, 2, 0, 3)
        self.has_atk_1 = False
        self.has_atk_2 = True
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard) -> Response:
        owner_card = card

        class _DamageRedirectModifier(AVGEModifier):
            def __init__(self):
                super().__init__(
                    identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, DanielZhu),
                    group=EngineGroup.EXTERNAL_MODIFIERS_2,
                )

            def event_match(self, event):
                from card_game.internal_events import AVGECardHPChange

                if not isinstance(event, AVGECardHPChange):
                    return False
                if event.target_card == owner_card:
                    return False
                if event.target_card.player == owner_card.player.opponent:
                    return False
                if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                    return False
                if owner_card.hp <= 1:
                    return False
                return True

            def event_effect(self) -> bool:
                return True

            def update_status(self):
                return


            def modify(self, args=None):
                if args is None:
                    args = {}
                from card_game.internal_events import InputEvent

                event = self.attached_event
                from card_game.internal_events import AVGECardHPChange
                assert isinstance(event, AVGECardHPChange)
                env = owner_card.env
                redirect_amount = env.cache.get(owner_card, DanielZhu._REDIRECT_KEY, None)
                if redirect_amount is None:
                    def is_valid(results):
                        if(len(results)!=1 or not isinstance(results[0], int)):
                            return False
                        return 0 <= results[0] <= max_redirect
                    incoming_damage = event.magnitude
                    max_redirect = min(30, incoming_damage, owner_card.hp - 1)
                    return self.generate_response(
                        ResponseType.INTERRUPT,
                        {
                            INTERRUPT_KEY: [
                                InputEvent(
                                    owner_card.player,
                                    [DanielZhu._REDIRECT_KEY],
                                    InputType.DETERMINISTIC,
                                    is_valid,
                                    ActionTypes.PASSIVE,
                                    owner_card,
                                    {
                                        LABEL_FLAG: "daniel_redirect",
                                        "maxdmg": max_redirect,
                                    },
                                )
                            ]
                        },
                    )

                redirect_damage = max(0, redirect_amount)
                event.modify_magnitude(-redirect_damage)
                return self.generate_response()

        class _DamageRedirectReactor(AVGEReactor):
            def __init__(self):
                super().__init__(
                    identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, DanielZhu),
                    group=EngineGroup.EXTERNAL_REACTORS,
                )

            def event_match(self, event):
                from card_game.internal_events import AVGECardHPChange

                if not isinstance(event, AVGECardHPChange):
                    return False
                if event.target_card == owner_card:
                    return False
                if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
                    return False
                if owner_card.hp <= 1:
                    return False
                return True

            def event_effect(self) -> bool:
                return owner_card.env.cache.get(owner_card, DanielZhu._REDIRECT_KEY, 0) != 0

            def update_status(self):
                return


            def react(self, args=None):
                if args is None:
                    args = {}
                from card_game.internal_events import AVGECardHPChange

                redirect_amount = owner_card.env.cache.get(owner_card, DanielZhu._REDIRECT_KEY, 0, True)
                assert isinstance(redirect_amount, int)
                owner_card.propose(
                    AVGEPacket([
                        AVGECardHPChange(
                            owner_card,
                            redirect_amount,
                            AVGEAttributeModifier.SUBSTRACTIVE,
                            CardType.WOODWIND,
                            ActionTypes.PASSIVE,
                            owner_card,
                        )
                    ], AVGEEngineID(owner_card, ActionTypes.PASSIVE, DanielZhu))
                )
                return self.generate_response()

        owner_card.add_listener(_DamageRedirectModifier())
        owner_card.add_listener(_DamageRedirectReactor())
        return owner_card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange, InputEvent

        roll = card.env.cache.get(card, DanielZhu._D6_ROLL_KEY, None, True)
        if roll is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [DanielZhu._D6_ROLL_KEY],
                            InputType.D6,
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            {LABEL_FLAG: "daniel_atk2_d6"},
                        )
                    ]
                },
            )

        damage = 30 + 10 * int(roll)
        def gen() -> PacketType:
            return [
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    damage,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_2,
                    card,
                )
            ]
        card.propose(
            AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_2, DanielZhu))
        )
        return card.generate_response()
