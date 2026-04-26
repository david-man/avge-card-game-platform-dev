from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import ActionTypes


class AntongChen(AVGECharacterCard):
    _ATK1_COIN_BASE = "antong_atk1_coin_"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.GUITAR, 2, 2, 3)
        self.atk_1_name = 'Fingerstyle'
        self.atk_2_name = "Power Chord"

    def atk_1(self, card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, AVGECardHPChange

        _, pc_used_last_turn_idx = card.env.check_history(
            card.env.round_id - 2,
            PlayCharacterCard,
            {
                "card": card,
                "card_action": ActionTypes.ATK_2,
                "caller": card
            },
        )
        if pc_used_last_turn_idx != -1:
            return Response(ResponseType.SKIP, Notify(f"{str(card)} tried to use Fingerstyle, but he couldn't!", all_players, default_timeout))

        coin_keys = [AntongChen._ATK1_COIN_BASE + str(i) for i in range(5)]
        vals = [card.env.cache.get(card, key, None, True) for key in coin_keys]
        if vals[0] is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[InputEvent]([
                        InputEvent(
                            card.player,
                            coin_keys,
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            CoinflipData("Fingerstyle: Flip a coin!")
                        )
                    ]),
            )
        heads = sum(int(v) for v in vals if v is not None)
        if heads <= 0:
            return Response(ResponseType.SKIP, Notify(f"{str(card)} used Fingerstyle, but he rolled 0 heads...", all_players, default_timeout))

        dmg = 20 * heads
        def gen() -> PacketType:
            return [
                AVGECardHPChange(
                card.player.opponent.get_active_card(),
                dmg,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.GUITAR,
                ActionTypes.ATK_1,
                None,
                card,
                )
            ]
        card.propose(AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_1, AntongChen)))

        return Response(ResponseType.SKIP, Notify(f"{str(card)} used Fingerstyle and rolled {heads} heads!", all_players, default_timeout))

    def atk_2(self, card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange, AVGEEnergyTransfer, EmptyEvent
        def generate_1() -> PacketType:
            return [AVGECardHPChange(
                        card.player.opponent.get_active_card(),
                        90,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.GUITAR,
                        ActionTypes.ATK_2,
                        None,
                        card,
                    )]
        def generate_2() -> PacketType:
            def discard_top() -> PacketType:
                if(len(card.energy) == 0):
                    return []
                else:
                    return [AVGEEnergyTransfer(card.energy[0], card, card.env, ActionTypes.ATK_2, card, None)]
            return [discard_top, discard_top]

        card.propose(AVGEPacket([generate_1, generate_2], AVGEEngineID(card, ActionTypes.ATK_2, AntongChen)))
        return Response(ResponseType.CORE, Notify(f"{str(card)} used Power Chord!", all_players, default_timeout))
