from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import AVGEReactor
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class JaydenBrown(AVGECharacterCard):
    _D6_ROLL_KEY = "jayden_d6_roll"
    _CHOICE = "jayden_coin_choice"

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

        class _CoinFlipReactor(AVGEReactor):
            def __init__(self):
                super().__init__(
                    identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, JaydenBrown),
                    group=EngineGroup.EXTERNAL_REACTORS,
                )

            def event_match(self, event):
                from card_game.internal_events import InputEvent

                if not isinstance(event, InputEvent):
                    return False
                if event.input_type != InputType.COIN:
                    return False
                if owner_card.cardholder is None or owner_card.cardholder.pile_type != Pile.ACTIVE:
                    return False
                return True

            def event_effect(self) -> bool:
                return True

            def update_status(self):
                return

            def make_announcement(self) -> bool:
                return True

            def package(self):
                return "JaydenBrown Coin Flip Reactor"

            def react(self, args=None):
                if args is None:
                    args = {}
                from card_game.internal_events import InputEvent

                env = owner_card.env
                event = self.attached_event
                assert isinstance(event, InputEvent)
                cache_key_used = f"jayden_coin_flip_used_turn_{env.round_id}"
                if env.cache.get(owner_card, cache_key_used, False, True):
                    return self.generate_response()

                env.cache.set(owner_card, cache_key_used, True)
                choice = env.cache.get(owner_card, JaydenBrown._CHOICE, None, True)
                if choice is None:
                    return self.generate_response(
                        ResponseType.INTERRUPT,
                        {
                            INTERRUPT_KEY: [
                                InputEvent(
                                    owner_card.player,
                                    [JaydenBrown._CHOICE],
                                    InputType.BINARY,
                                    lambda r: True,
                                    ActionTypes.PASSIVE,
                                    owner_card,
                                    {"query_label": "jayden_brown_coinflip"},
                                )
                            ]
                        },
                    )

                # Force the first coin outcome key for this coin input event.
                if len(event.input_keys) > 0:
                    env.cache.set(owner_card, event.input_keys[0], 1)
                return self.generate_response()

        owner_card.add_listener(_CoinFlipReactor())
        return owner_card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChangeCreator, InputEvent

        roll = card.env.cache.get(card, JaydenBrown._D6_ROLL_KEY, None, True)
        if roll is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [JaydenBrown._D6_ROLL_KEY],
                            InputType.D6,
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            {"query_label": "jaydenbrown_d6"},
                        )
                    ]
                },
            )

        damage = 30 + 10 * int(roll)
        card.propose(
            AVGEPacket([
                AVGECardHPChangeCreator(
                    lambda: card.player.opponent.get_active_card(),
                    damage,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_1,
                    card,
                )
            ], AVGEEngineID(card, ActionTypes.ATK_1, JaydenBrown))
        )
        return card.generate_response()
