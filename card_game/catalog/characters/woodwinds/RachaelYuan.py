from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import AVGECardHPChange, InputEvent, PlayCharacterCard, TransferCard, EmptyEvent

class RachaelYuan(AVGECharacterCard):
    _BENCH_SHUFFLE_KEY = 'rachaelyuan_bench_shuffle'

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.WOODWIND, 2, 1, 3)
        self.atk_1_name = 'Circular Breathing'
        self.atk_2_name = 'E2 Reaction'

    def atk_1(self, card: AVGECharacterCard) -> Response:
        streak = 0
        turn = card.player.get_last_turn()
        while streak < 4 and turn >= 0:
            _, used_last_turn_idx = card.env.check_history(
                turn,
                PlayCharacterCard,
                {
                    'card': card,
                    'card_action': ActionTypes.ATK_1,
                    'caller': card,
                },
            )
            if used_last_turn_idx == -1:
                break
            streak += 1
            turn -= 2

        total_damage = 10 + (10 * streak)

        def generate_packet() -> PacketType:
            packet: PacketType = []
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        total_damage,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.WOODWIND,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, RachaelYuan)))
        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard) -> Response:
        opponent = card.player.opponent
        opponent_bench = opponent.cardholders[Pile.BENCH]
        opponent_deck = opponent.cardholders[Pile.DECK]
        if(len(opponent_bench) < 2):
            card.propose(AVGEPacket([EmptyEvent(
                ActionTypes.ATK_2,
                card,
                ResponseType.CORE,
                Notify(f"{str(card)} used E2 Reaction, but it didn't do anything...", all_players, default_timeout)
            )], AVGEEngineID(card, ActionTypes.ATK_2, RachaelYuan)))
            return Response(ResponseType.CORE, Data())
        missing = object()
        chosen_card = card.env.cache.get(card, RachaelYuan._BENCH_SHUFFLE_KEY, missing, True)
        if len(opponent_bench) >= 2 and chosen_card is missing:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                    InputEvent(
                        card.player,
                        [RachaelYuan._BENCH_SHUFFLE_KEY],
                        lambda r: True,
                        ActionTypes.ATK_2,
                        card,
                        CardSelectionQuery(
                            'E2 Reaction: You may shuffle one opposing benched character into their deck.',
                            list(opponent_bench),
                            list(opponent_bench),
                            True,
                            False,
                        )
                    )
                ]),
            )

        def generate_packet() -> PacketType:
            packet: PacketType = []
            if len(opponent_bench) >= 2 and isinstance(chosen_card, AVGECharacterCard) and chosen_card in opponent_bench:
                packet.append(
                    TransferCard(
                        chosen_card,
                        opponent_bench,
                        opponent_deck,
                        ActionTypes.ATK_2,
                        card,
                        None,
                        random.randint(0, len(opponent_deck)),
                    )
                )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_2, RachaelYuan)))
        return self.generic_response(card, ActionTypes.ATK_2)
