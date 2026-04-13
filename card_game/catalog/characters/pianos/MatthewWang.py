from __future__ import annotations

from card_game.avge_abstracts import *

from card_game.constants import *
from card_game.engine.engine_constants import *


class _MatthewTurnBeginReactor(AVGEReactor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, MatthewWang), group=EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card

    def event_match(self, event):
        from card_game.internal_events import PhasePickCard

        return isinstance(event, PhasePickCard) and self.owner_card.player == self.owner_card.env.player_turn and self.owner_card == self.owner_card.player.get_active_card()

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def react(self, args=None):
        if args is None:
            args = {}
        from card_game.internal_events import InputEvent, TransferCard

        owner = self.owner_card
        env = owner.env
        deck = owner.player.cardholders[Pile.DECK]
        if len(deck) == 0:
            return self.generate_response(data={MESSAGE_KEY: "No cards in deck to draw from!"})

        res = env.cache.get(owner, MatthewWang._COIN_KEY, None)
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
                            {LABEL_FLAG: "matthew_wang_1coin"},
                        )
                    ]
                },
            )

        if int(res) != 1:
            env.cache.delete(owner, MatthewWang._COIN_KEY)
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
                            {LABEL_FLAG: "matthew_wang_successful_coin"},
                        )
                    ]
                },
            )
        env.cache.delete(owner, MatthewWang._COIN_KEY)
        if choice == 1:
            def draw_top() -> PacketType:
                if len(deck) == 0:
                    return []
                return [
                    TransferCard(
                        deck.peek(),
                        deck,
                        owner.player.cardholders[Pile.HAND],
                        ActionTypes.PASSIVE,
                        owner,
                    )
                ]

            owner.propose(
                AVGEPacket([
                    draw_top
                ], AVGEEngineID(owner, ActionTypes.PASSIVE, MatthewWang)), 1
            )

        return self.generate_response()


class MatthewWang(AVGECharacterCard):
    _COIN_KEY = "matthew_coin"
    _DRAW_CHOICE_KEY = "matthew_draw_choice"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.PIANO, 2, 3)
        self.has_atk_1 = True
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard) -> Response:
        card.add_listener(_MatthewTurnBeginReactor(card))
        return card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        def generate_packet() -> PacketType:
            active = card.player.opponent.get_active_card()
            if not isinstance(active, AVGECharacterCard):
                return []
            return [
                AVGECardHPChange(
                    active,
                    60,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PIANO,
                    ActionTypes.ATK_1,
                    card,
                )
            ]

        card.propose(
            AVGEPacket([
                generate_packet
            ], AVGEEngineID(card, ActionTypes.ATK_1, MatthewWang))
        )

        return card.generate_response()
