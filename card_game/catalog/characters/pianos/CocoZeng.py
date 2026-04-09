from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class CocoZeng(AVGECharacterCard):
    _LAST_ATK1_ROUND_KEY = "cocozeng_atk1_last_round"
    _ATK2_COIN_BASE = "cocozeng_atk2_coin_"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.PIANO, 2, 1, 3)
        self.has_atk_1 = True
        self.has_atk_2 = True
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange, EmptyEvent

        last_round = card.env.cache.get(card, CocoZeng._LAST_ATK1_ROUND_KEY, None)
        if last_round is not None and card.env.round_id - last_round <= 2:
            return card.generate_response(data={MESSAGE_KEY: "You cannot use this attack this turn!"})
        def gen() -> PacketType:
            return [
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    30,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PIANO,
                    ActionTypes.ATK_1,
                    card,
                )
            ]
        card.propose(
            AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_1, CocoZeng))
        )

        card.env.cache.set(card, CocoZeng._LAST_ATK1_ROUND_KEY, card.env.round_id)
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, AVGECardHPChange

        n = len(card.player.cardholders[Pile.HAND])
        if n == 0:
            return card.generate_response(data={MESSAGE_KEY: "Nothing in hand!"})

        coin_keys = [CocoZeng._ATK2_COIN_BASE + str(i) for i in range(n)]
        vals = [card.env.cache.get(card, key, None, True) for key in coin_keys]
        if vals[0] is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            coin_keys,
                            InputType.COIN,
                            lambda res: True,
                            ActionTypes.ATK_2,
                            card,
                            {"query_label": "cocozeng_inventory_management"},
                        )
                    ]
                },
            )

        heads = sum(int(v) for v in vals if v is not None)
        if heads <= 0:
            return card.generate_response()
        def gen() -> PacketType:
            return [AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    30 * heads,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PIANO,
                    ActionTypes.ATK_2,
                    card,
                )]
        card.propose(
            AVGEPacket([
                gen
            ], AVGEEngineID(card, ActionTypes.ATK_2, CocoZeng))
        )

        return card.generate_response()
