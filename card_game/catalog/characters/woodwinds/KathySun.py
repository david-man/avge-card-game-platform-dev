from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import AVGECardHPChange, EmptyEvent, InputEvent, TransferCard

class KathySun(AVGECharacterCard):
    _OPPONENT_SHUFFLE_KEY = 'kathysun_opponent_shuffle_selection_'
    _D6_ROLL_KEY = 'kathysun_d6_roll'
    _PREV_ROLL_KEY = 'kathysun_prev_roll'
    _ROLL_COUNT_KEY = 'kathysun_roll_count'

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.WOODWIND, 1, 1, 3)
        self.atk_1_name = 'Analysis Paralysis'
        self.atk_2_name = 'Flutter Tongue'

    def atk_1(self, card: AVGECharacterCard) -> Response:
        opponent = card.player.opponent
        opponent_hand = opponent.cardholders[Pile.HAND]
        opponent_deck = opponent.cardholders[Pile.DECK]

        choose_count = min(2, len(opponent_hand))
        if choose_count == 0:
            return Response(ResponseType.CORE, Notify(f"{str(card)} tried to use Analysis Paralysis, but it did nothing...", all_players, default_timeout))

        keys = [KathySun._OPPONENT_SHUFFLE_KEY + str(i) for i in range(choose_count)]
        selected = [card.env.cache.get(card, key, None, True) for key in keys]
        if selected[0] is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        EmptyEvent(
                            ActionTypes.ATK_1,
                            card,
                            ResponseType.CORE,
                            RevealCards(
                                'Analysis Paralysis: Opponent hand',
                                [card.player.unique_id],
                                default_timeout,
                                list(opponent_hand),
                            ),
                        ),
                        InputEvent(
                            opponent,
                            keys,
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            CardSelectionQuery(
                                'Analysis Paralysis: Choose cards to shuffle into your deck.',
                                list(opponent_hand),
                                list(opponent_hand),
                                False,
                                False,
                            )
                        )
                    ]),
            )

        def generate_packet(chosen_card: AVGECard | None) -> PacketType:
            packet: PacketType = []
            if isinstance(chosen_card, AVGECard):
                packet.append(
                    TransferCard(
                        chosen_card,
                        opponent_hand,
                        opponent_deck,
                        ActionTypes.ATK_1,
                        card,
                        None,
                        random.randint(0, len(opponent_deck)),
                    )
                )
            return packet

        packet: PacketType = [lambda chosen=choice: generate_packet(chosen) for choice in selected]
        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, KathySun)))
        return self.generic_response(card, ActionTypes.ATK_1)

    def _roll_interrupt(self, card: AVGECharacterCard) -> Response:
        return Response(
            ResponseType.INTERRUPT,
            Interrupt[AVGEEvent]([
                InputEvent(
                    card.player,
                    [KathySun._D6_ROLL_KEY],
                    lambda r: True,
                    ActionTypes.ATK_2,
                    card,
                    D6Data('Flutter Tongue: Roll a D6.'),
                )
            ]),
        )

    def atk_2(self, card: AVGECharacterCard) -> Response:
        missing = object()
        roll = card.env.cache.get(card, KathySun._D6_ROLL_KEY, missing, True)
        if roll is missing:
            return self._roll_interrupt(card)
        assert isinstance(roll, int)

        prev_roll = card.env.cache.get(card, KathySun._PREV_ROLL_KEY, None, True)
        roll_count = card.env.cache.get(card, KathySun._ROLL_COUNT_KEY, 0, True)
        assert isinstance(roll_count, int)
        roll_count += 1

        is_done = isinstance(prev_roll, int) and (prev_roll + roll == 7)
        if not is_done:
            card.env.cache.set(card, KathySun._PREV_ROLL_KEY, roll)
            card.env.cache.set(card, KathySun._ROLL_COUNT_KEY, roll_count)
            return self._roll_interrupt(card)

        def one_hit() -> PacketType:
            packet: PacketType = []
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        10,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.WOODWIND,
                        ActionTypes.ATK_2,
                        None,
                        card,
                    )
                )
            return packet

        packet: PacketType = [one_hit for _ in range(roll_count)]
        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_2, KathySun)))
        return self.generic_response(card, ActionTypes.ATK_2)
