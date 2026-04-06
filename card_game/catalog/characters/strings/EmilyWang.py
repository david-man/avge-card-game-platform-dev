from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *
from card_game.avge_abstracts.AVGEEnvironment import GamePhase


class EmilyWang(AVGECharacterCard):
    _ACTIVE_DISCARD_KEY = "emilywang_active_discard_tool"
    _COIN_KEY_0 = "emilywang_coin_0"
    _COIN_KEY_1 = "emilywang_coin_1"
    _COIN_KEY_2 = "emilywang_coin_2"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 1, 3)
        self.has_atk_1 = True
        self.atk_1_cost = 3
        self.has_atk_2 = False
        self.has_passive = False
        self.has_active = True

    @staticmethod
    def can_play_active(card: AVGECharacterCard) -> bool:
        env = card.env
        if env is None or card.player is None:
            return False
        if env.game_phase != GamePhase.ATK_PHASE:
            return False
        if env.player_turn != card.player:
            return False
        return len(card.tools_attached) > 0

    @staticmethod
    def active(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import TransferCardCreator, InputEvent

        tool = card.tools_attached.peek()
        chosen = card.env.cache.get(card, EmilyWang._ACTIVE_DISCARD_KEY, None, True)
        if chosen is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [EmilyWang._ACTIVE_DISCARD_KEY],
                            InputType.BINARY,
                            lambda r: True,
                            ActionTypes.ACTIVATE_ABILITY,
                            card,
                            {"query_type": "emily_wang_tool_discard"},
                        )
                    ]
                },
            )

        discard = card.player.cardholders[Pile.DISCARD]
        packet = [TransferCardCreator(tool, tool.cardholder, discard, ActionTypes.ACTIVATE_ABILITY, card)]

        deck = card.player.cardholders[Pile.DECK]
        hand = card.player.cardholders[Pile.HAND]
        for _ in range(min(2, len(deck))):
            packet.append(TransferCardCreator(lambda: deck.peek(), deck, hand, ActionTypes.ACTIVATE_ABILITY, card))

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ACTIVATE_ABILITY, EmilyWang)))
        return card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChangeCreator, InputEvent

        r0 = card.env.cache.get(card, EmilyWang._COIN_KEY_0, None, True)
        r1 = card.env.cache.get(card, EmilyWang._COIN_KEY_1, None, True)
        r2 = card.env.cache.get(card, EmilyWang._COIN_KEY_2, None, True)
        if r0 is None or r1 is None or r2 is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [EmilyWang._COIN_KEY_0, EmilyWang._COIN_KEY_1, EmilyWang._COIN_KEY_2],
                            InputType.COIN,
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            {"query_label": "emily_wang_triple_stop"},
                        )
                    ]
                },
            )

        heads = int(r0) + int(r1) + int(r2)
        if heads > 0:
            card.propose(
                AVGEPacket([
                    AVGECardHPChangeCreator(
                        lambda: card.player.opponent.get_active_card(),
                        40 * heads,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.STRING,
                        ActionTypes.ATK_1,
                        card,
                    )
                ], AVGEEngineID(card, ActionTypes.ATK_1, EmilyWang))
            )

        return card.generate_response()
