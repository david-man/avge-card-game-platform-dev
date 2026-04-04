from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *
from card_game.engine.engine_constants import *


class _MatthewTurnBeginReactor(AVGEReactor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=(owner_card, AVGEEventListenerType.PASSIVE), group=EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card

    def event_match(self, event):
        from card_game.internal_events import PhasePickCard

        return isinstance(event, PhasePickCard) and self.owner_card.player != self.owner_card.env.player_turn and self.owner_card == self.owner_card.player.get_active_card()

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return True

    def package(self):
        return "MatthewWang turn-begin reactor"

    def react(self, args=None):
        if args is None:
            args = {}
        from card_game.internal_events import InputEvent, TransferCard

        owner = self.owner_card
        env = owner.env
        deck = owner.player.cardholders[Pile.DECK]
        if len(deck) == 0:
            return self.generate_response()

        res = env.cache.get(owner, MatthewWang._COIN_KEY, None, True)
        if res is None:
            return owner.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            owner.player,
                            [MatthewWang._COIN_KEY],
                            InputType.COIN,
                            lambda r: True,
                            ActionTypes.PASSIVE,
                            owner,
                            {"query_label": "matthew-wang-1coin"},
                        )
                    ]
                },
            )

        if int(res) != 1:
            return self.generate_response()

        choice = env.cache.get(owner, MatthewWang._DRAW_CHOICE_KEY, None, True)
        if choice is None:
            return owner.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            owner.player,
                            [MatthewWang._DRAW_CHOICE_KEY],
                            InputType.BINARY,
                            lambda r: True,
                            ActionTypes.PASSIVE,
                            owner,
                            {"query_label": "matthew-successful-coin"},
                        )
                    ]
                },
            )

        if choice == 1:
            owner.propose(TransferCard(lambda: deck.peek(), deck, owner.player.cardholders[Pile.HAND], ActionTypes.PASSIVE, owner))

        return self.generate_response()


class MatthewWang(AVGECharacterCard):
    _COIN_KEY = "matthew_coin"
    _DRAW_CHOICE_KEY = "matthew_draw_choice"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.PIANO, 2, 3)
        self.has_atk_1 = True
        self.atk_1_cost = 3
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        card.add_listener(_MatthewTurnBeginReactor(card))
        return card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import AVGECardHPChange

        card.propose(
            AVGECardHPChange(
                lambda: card.player.opponent.get_active_card(),
                60,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.PIANO,
                ActionTypes.ATK_1,
                card,
            )
        )

        return card.generate_response()
