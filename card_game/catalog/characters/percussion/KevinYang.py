from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import InputEvent, AVGECardHPChange


class KevinYang(AVGECharacterCard):
    _D6_KEY = "kevin_d6_roll"
    _D6_KEYS_4 = [f"kevin_d6_roll_{i}" for i in range(4)]

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.PERCUSSION, 2, 2, 3)
        self.atk_1_name = 'Rimshot'
        self.atk_2_name = 'Stickshot'

    def atk_1(self, card: AVGECharacterCard) -> Response:
        missing = object()
        roll = card.env.cache.get(card, KevinYang._D6_KEY, missing, True)
        if roll is missing:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [KevinYang._D6_KEY],
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            D6Data('Rimshot: Roll a dice!')
                        )
                    ]),
            )

        if not isinstance(roll, int):
            return self.generic_response(card, ActionTypes.ATK_1)

        val = int(roll)
        if val <= 4:
            def gen() -> PacketType:
                packet: PacketType = []
                packet.append(
                    AVGECardHPChange(
                        card.player.opponent.get_active_card(),
                        60,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.PERCUSSION,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )
                return packet
            card.propose(
                AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_1, KevinYang))
            )

        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard) -> Response:
        missing = object()
        rolls = [card.env.cache.get(card, key, missing, True) for key in KevinYang._D6_KEYS_4]
        if any(r is missing for r in rolls):
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            KevinYang._D6_KEYS_4,
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            D6Data('Stickshot: Roll a dice four times!')
                        )
                    ]),
            )

        if not all(isinstance(v, int) for v in rolls):
            return self.generic_response(card, ActionTypes.ATK_2)

        int_rolls = [int(v) for v in rolls if isinstance(v, int)]
        lowest = min(int_rolls)
        damage = 40 * lowest
        def gen() -> PacketType:
            packet: PacketType = []
            packet.append(
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    damage,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PERCUSSION,
                    ActionTypes.ATK_2,
                    None,
                    card,
                )
            )
            return packet
        card.propose(
            AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_2, KevinYang))
        )

        return Response(ResponseType.CORE, Notify(
            f"{str(card)} used Stickshot and rolled a {lowest} as his lowest roll", all_players, default_timeout
        ))
