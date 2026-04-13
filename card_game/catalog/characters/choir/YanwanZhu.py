from __future__ import annotations

from typing import cast

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class _YanwanStartReactor(AVGEReactor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, YanwanZhu), group=EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card

    def event_match(self, event):
        from card_game.internal_events import PhasePickCard

        if not isinstance(event, PhasePickCard):
            return False
        if self.owner_card.cardholder.pile_type != Pile.ACTIVE:
            return False
        if (event.player == self.owner_card.player and len(self.owner_card.player.cardholders[Pile.DECK]) <= 1):
            return False
        if (event.player.opponent == self.owner_card.player and len(self.owner_card.player.cardholders[Pile.DECK]) == 0):
            return False
        if len(self.owner_card.energy) != 2:
            return False

        return True

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def react(self, args=None):
        from card_game.internal_events import InputEvent, TransferCard

        owner = self.owner_card
        env = owner.env
        deck = owner.player.cardholders[Pile.DECK]
        hand = owner.player.cardholders[Pile.HAND]
        if(len(deck) == 0):
            return self.generate_response()
        yn = env.cache.get(owner, YanwanZhu._DRAW_CHOICE_KEY, None, True)
        if yn is None:
            return owner.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            owner.player,
                            [YanwanZhu._DRAW_CHOICE_KEY],
                            InputType.BINARY,
                            lambda r: True,
                            ActionTypes.PASSIVE,
                            owner,
                            {LABEL_FLAG: "yanwan_optional_draw"},
                        )
                    ]
                },
            )
        if yn:
            def generate() -> PacketType:
                if(len(deck) > 0):
                    return [TransferCard(deck.peek(), deck, hand, ActionTypes.PASSIVE, owner)]
                return []
            self.propose(
                AVGEPacket(
                    [generate],
                    AVGEEngineID(owner, ActionTypes.PASSIVE, YanwanZhu),
                ), 1
            )
        return self.generate_response()


class YanwanZhu(AVGECharacterCard):
    _DRAW_CHOICE_KEY = "yanwan_draw_choice"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.CHOIR, 1, 1)
        self.has_atk_1 = True
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard) -> Response:
        card.add_listener(_YanwanStartReactor(card))
        return card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange
        def gen_active() -> PacketType:
            return [
                    AVGECardHPChange(
                        card.player.opponent.get_active_card(),
                        50,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.CHOIR,
                        ActionTypes.ATK_1,
                        card,
                    )
                ]
        def gen_bench() -> PacketType:
            p : PacketType = [
                    AVGECardHPChange(
                        cast(AVGECharacterCard, c),
                        10,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.CHOIR,
                        ActionTypes.ATK_1,
                        card,
                    ) for c in card.player.opponent.cardholders[Pile.BENCH]
                ]
            return p
        card.propose(
            AVGEPacket(
                [gen_active, gen_bench],
                AVGEEngineID(card, ActionTypes.ATK_1, YanwanZhu),
            )
        )

        return card.generate_response()
