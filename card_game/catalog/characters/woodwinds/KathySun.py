from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class KathySun(AVGECharacterCard):
    _OPPONENT_SHUFFLE_KEY = "kathysun_opponent_shuffle_selection_"
    _D6_ROLL_KEY = "kathysun_runtime_d6_roll"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.WOODWIND, 1, 1, 3)
        self.has_atk_1 = True
        self.has_atk_2 = True
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, TransferCard, EmptyEvent

        opponent = card.player.opponent
        opponent_hand = opponent.cardholders[Pile.HAND]
        opponent_deck = opponent.cardholders[Pile.DECK]

        keys = [KathySun._OPPONENT_SHUFFLE_KEY + str(i) for i in range(min(2, len(opponent.cardholders[Pile.HAND])))]
        shuffle = [card.env.cache.get(card, key , None, True)  for key in keys]
        if shuffle[0] is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        EmptyEvent(
                            ActionTypes.ATK_1,
                            card,
                            response_data={
                                REVEAL_KEY: list(opponent_hand)
                            }
                        ),
                        InputEvent(
                            opponent,
                            keys,
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            {
                                LABEL_FLAG: "kathy_sun_opponent_shuffle",
                                TARGETS_FLAG: list(opponent_hand),
                                DISPLAY_FLAG: list(opponent_hand),
                            },
                        )
                    ]
                },
            )
        def generate_packet(chosen_card) -> PacketType:
            packet: PacketType = []
            if isinstance(chosen_card, AVGECard):
                packet.append(
                    TransferCard(
                        chosen_card,
                        opponent_hand,
                        opponent_deck,
                        ActionTypes.ATK_1,
                        card,
                        random.randint(0, len(opponent_deck)),
                    )
                )
            return packet
        
        packet : PacketType = [lambda chosen=selected: generate_packet(chosen) for selected in shuffle]
        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, KathySun)))
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange, InputEvent

        roll = card.env.cache.get(card, KathySun._D6_ROLL_KEY, None, True)
        if roll is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [KathySun._D6_ROLL_KEY],
                            InputType.D6,
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            {LABEL_FLAG: "kathy_sun_d6"},
                        )
                    ]
                },
            )

        damage = 30 + 10 * int(roll)
        def generate_packet() -> PacketType:
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                return [
                    AVGECardHPChange(
                        active,
                        damage,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.WOODWIND,
                        ActionTypes.ATK_2,
                        card,
                    )
                ]
            return []

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_2, KathySun)))
        return card.generate_response()
