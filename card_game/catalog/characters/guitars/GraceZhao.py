from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.catalog.tools import AVGEShowcaseSticker, AVGETShirt


class _GraceTurnEndReactor(AVGEReactor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=(owner_card, AVGEEventListenerType.PASSIVE), group=EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card

    def event_match(self, event):
        from card_game.internal_events import TurnEnd

        if not isinstance(event, TurnEnd):
            return False
        if self.owner_card.cardholder is None or self.owner_card.cardholder.pile_type not in [Pile.ACTIVE, Pile.BENCH]:
            return False
        if self.owner_card.player is None or self.owner_card.player.opponent is None:
            return False
        if event.env.player_turn == self.owner_card.player:
            return False

        opponent = self.owner_card.player.opponent
        for c in opponent.get_cards_in_play():
            for t in c.tools_attached:
                if isinstance(t, (AVGEShowcaseSticker, AVGETShirt)):
                    return True
        return False

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return True

    def package(self):
        return "GraceZhao TurnEnd Reactor"

    def react(self, args=None):
        if args is None:
            args = {}
        from card_game.internal_events import InputEvent, AVGECardHPChange

        opponent = self.owner_card.player.opponent
        candidates = []
        for c in opponent.get_cards_in_play():
            for t in c.tools_attached:
                if isinstance(t, (AVGEShowcaseSticker, AVGETShirt)):
                    candidates.append(c)
                    break

        selected_card = self.owner_card.env.cache.get(self.owner_card, GraceZhao._TARGET_KEY, None, True)
        if selected_card is None:
            return self.owner_card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            self.owner_card.player,
                            [GraceZhao._TARGET_KEY],
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.PASSIVE,
                            self.owner_card,
                            {
                                "query_label": "grace-choice",
                                "targets": candidates,
                            },
                        )
                    ]
                },
            )

        self.propose(
            AVGECardHPChange(
                selected_card,
                10,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.GUITAR,
                ActionTypes.PASSIVE,
                self.owner_card,
            )
        )
        return self.generate_response()


class GraceZhao(AVGECharacterCard):
    _TARGET_KEY = "grace-target-key-atk1"

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.GUITAR, 2, 2)
        self.has_atk_1 = True
        self.atk_1_cost = 2
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        card.add_listener(_GraceTurnEndReactor(card))
        return card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import AVGECardHPChange

        packet = [
            AVGECardHPChange(
                lambda: card.player.opponent.get_active_card(),
                50,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.GUITAR,
                ActionTypes.ATK_1,
                card,
            )
        ]

        for c in card.player.cardholders[Pile.BENCH]:
            if isinstance(c, AVGECharacterCard) and c.card_type == CardType.GUITAR:
                packet.append(
                    AVGECardHPChange(
                        c,
                        10,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.GUITAR,
                        ActionTypes.ATK_1,
                        card,
                    )
                )

        card.propose(packet)
        return card.generate_response()
