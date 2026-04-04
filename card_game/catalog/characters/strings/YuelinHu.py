from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *
from card_game.engine.engine_constants import *


class YuelinHu(AVGECharacterCard):
    _DISCARD_DECISION_KEY = "yuelinhu_discard_decision"
    _DISCARD_TARGET_KEY = "yuelinhu_discard_target"
    _COIN_KEY_0 = "yuelinhu_coin_0"
    _COIN_KEY_1 = "yuelinhu_coin_1"
    _COIN_KEY_2 = "yuelinhu_coin_2"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 1, 3)
        self.has_atk_1 = True
        self.atk_1_cost = 3
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        owner_card = card

        class _BirbDrawReactor(AVGEReactor):
            def __init__(self):
                super().__init__(identifier=(owner_card, AVGEEventListenerType.PASSIVE), group=EngineGroup.EXTERNAL_REACTORS)
                self.owner_card = owner_card

            def event_match(self, event):
                from card_game.internal_events import TransferCard
                from card_game.catalog.items.AVGEBirb import AVGEBirb

                if not isinstance(event, TransferCard):
                    return False
                if not isinstance(event.card, AVGEBirb):
                    return False
                if event.pile_from.pile_type != Pile.DECK:
                    return False
                if event.pile_to.pile_type != Pile.HAND:
                    return False
                return event.pile_to.player == self.owner_card.player

            def event_effect(self) -> bool:
                return True

            def update_status(self):
                return

            def make_announcement(self) -> bool:
                return True

            def package(self):
                return "YuelinHu Birb Draw Reactor"

            def react(self, args=None):
                if args is None:
                    args = {}
                from card_game.internal_events import AVGECardHPChange, InputEvent, TransferCard

                env = self.owner_card.env
                player = self.owner_card.player
                hand = player.cardholders[Pile.HAND]
                discard = player.cardholders[Pile.DISCARD]

                should_discard = env.cache.get(self.owner_card, YuelinHu._DISCARD_DECISION_KEY, None, True)
                if should_discard is None:
                    return self.generate_response(
                        ResponseType.INTERRUPT,
                        {
                            INTERRUPT_KEY: [
                                InputEvent(
                                    player,
                                    [YuelinHu._DISCARD_DECISION_KEY],
                                    InputType.BINARY,
                                    lambda r: True,
                                    ActionTypes.NONCHAR,
                                    self.owner_card,
                                    {
                                        "query_label": "yuelin_hu_birb_reactor",
                                    },
                                )
                            ]
                        },
                    )

                if not should_discard or len(hand) == 0:
                    return self.generate_response()

                discard_target = env.cache.get(self.owner_card, YuelinHu._DISCARD_TARGET_KEY, None, True)
                if discard_target is None:
                    return self.generate_response(
                        ResponseType.INTERRUPT,
                        {
                            INTERRUPT_KEY: [
                                InputEvent(
                                    player,
                                    [YuelinHu._DISCARD_TARGET_KEY],
                                    InputType.SELECTION,
                                    lambda r: True,
                                    ActionTypes.NONCHAR,
                                    self.owner_card,
                                    {
                                        "query_label": "yuelin_hu_birb_reactor_discard",
                                        "targets": list(hand),
                                    },
                                )
                            ]
                        },
                    )

                packet = [
                    TransferCard(discard_target, hand, discard, ActionTypes.PASSIVE, self.owner_card),
                    AVGECardHPChange(
                        lambda: player.opponent.get_active_card(),
                        40,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.STRING,
                        ActionTypes.PASSIVE,
                        self.owner_card,
                    ),
                ]
                self.propose(packet)
                return self.generate_response()

        owner_card.add_listener(_BirbDrawReactor())
        return owner_card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import AVGECardHPChange, InputEvent

        r0 = card.env.cache.get(card, YuelinHu._COIN_KEY_0, None, True)
        r1 = card.env.cache.get(card, YuelinHu._COIN_KEY_1, None, True)
        r2 = card.env.cache.get(card, YuelinHu._COIN_KEY_2, None, True)
        if r0 is None or r1 is None or r2 is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [YuelinHu._COIN_KEY_0, YuelinHu._COIN_KEY_1, YuelinHu._COIN_KEY_2],
                            InputType.COIN,
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            {"query_label": "yuelin_hu_triple_stop"},
                        )
                    ]
                },
            )

        heads = r0 + r1 + r2

        for _ in range(heads):
            card.propose(
                AVGECardHPChange(
                    lambda: card.player.opponent.get_active_card(),
                    40,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.STRING,
                    ActionTypes.ATK_1,
                    card,
                )
            )

        return card.generate_response()
