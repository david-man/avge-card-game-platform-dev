from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import ActionTypes


class AntongChen(AVGECharacterCard):
    _LAST_ATK2_ROUND_KEY = "antong_last_atk2_round"
    _ATK1_COIN_BASE = "antong_atk1_coin_"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.GUITAR, 2, 2, 3)
        self.has_atk_1 = True
        self.has_atk_2 = True
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, AVGECardHPChange

        last_atk2 = card.env.cache.get(card, AntongChen._LAST_ATK2_ROUND_KEY, None)
        if last_atk2 is not None and card.env.round_id - last_atk2 <= 2:
            return card.generate_response(data={MESSAGE_KEY: "Cannot use this attack this turn!"})

        coin_keys = [AntongChen._ATK1_COIN_BASE + str(i) for i in range(5)]
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
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            {LABEL_FLAG: "antong_chen_5coin"},
                        )
                    ]
                },
            )
        heads = sum(int(v) for v in vals if v is not None)
        if heads <= 0:
            return card.generate_response()

        dmg = 20 * heads
        def gen() -> PacketType:
            return [
                AVGECardHPChange(
                card.player.opponent.get_active_card(),
                dmg,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.GUITAR,
                ActionTypes.ATK_1,
                card,
                )
            ]
        card.propose(AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_1, AntongChen)))

        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange, AVGEEnergyTransfer, EmptyEvent
        def generate_1() -> PacketType:
            return [AVGECardHPChange(
                        card.player.opponent.get_active_card(),
                        90,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.GUITAR,
                        ActionTypes.ATK_2,
                        card,
                    )]
        def generate_2() -> PacketType:
            def discard_top() -> PacketType:
                if(len(card.energy) == 0):
                    return []
                else:
                    return [AVGEEnergyTransfer(card.energy[0], card, card.env, ActionTypes.ATK_2, card)]
            return [discard_top, discard_top]

        card.env.cache.set(card, AntongChen._LAST_ATK2_ROUND_KEY, card.env.round_id)
        card.propose(AVGEPacket([generate_1, generate_2], AVGEEngineID(card, ActionTypes.ATK_2, AntongChen)))
        return card.generate_response()
