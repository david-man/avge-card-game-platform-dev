from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes

class IzzyChen(AVGECharacterCard):
    _COIN_FLIP_1_KEY = "izzy_coin_flip_1"
    _COIN_FLIP_2_KEY = "izzy_coin_flip_2"
    _ACTIVE_USED_KEY = "izzy_active_used"
    _ACTIVE_STADIUM_CHOICE = "izzy_stadium_choice"

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.WOODWIND, 2, 0, 3)
        self.has_atk_1 = False
        self.has_atk_2 = True
        self.atk_2_cost = 3
        self.has_passive = False
        self.has_active = True

    @staticmethod
    def can_play_active(card) -> bool:
        already_used = card.env.cache.get(card, IzzyChen._ACTIVE_USED_KEY, None, True)
        if card.env.round_id == already_used:
            return False
        discard = card.player.cardholders[Pile.DISCARD]
        return any(isinstance(c, AVGEStadiumCard) for c in discard.cards_by_id.values())

    @staticmethod
    def active(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, TransferCard

        player = card.player
        discard = player.cardholders[Pile.DISCARD]
        deck = player.cardholders[Pile.DECK]
        stadiums = [c for c in discard.cards_by_id.values() if isinstance(c, AVGEStadiumCard)]
        if len(stadiums) == 0:
            return card.generate_response()
        chosen_stadium = card.env.cache.get(card, IzzyChen._ACTIVE_STADIUM_CHOICE, None, True)
        if chosen_stadium is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            player,
                            [IzzyChen._ACTIVE_STADIUM_CHOICE],
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ACTIVATE_ABILITY,
                            card,
                            {
                                "query_label": "izzy_stadium_recover",
                                "targets": stadiums,
                                "display": list(discard)
                            },
                        )
                    ]
                },
            )

        card.propose(AVGEPacket([TransferCard(chosen_stadium, discard, deck, ActionTypes.ACTIVATE_ABILITY, card, 0)], AVGEEngineID(card, ActionTypes.ACTIVATE_ABILITY, IzzyChen)))
        card.env.cache.set(card, IzzyChen._ACTIVE_USED_KEY, card.env.round_id)
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange, InputEvent

        opponent_bench = card.player.opponent.cardholders[Pile.BENCH]
        flip_result_1 = card.env.cache.get(card, IzzyChen._COIN_FLIP_1_KEY, None, True)
        flip_result_2 = card.env.cache.get(card, IzzyChen._COIN_FLIP_2_KEY, None, True)
        if flip_result_1 is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [IzzyChen._COIN_FLIP_1_KEY, IzzyChen._COIN_FLIP_2_KEY],
                            InputType.COIN,
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            {"query_label": "izzychen_2coin"},
                        )
                    ]
                },
            )

        if flip_result_1 == 1 and flip_result_2 == 1:
            damage = 50
        elif flip_result_1 == 0 and flip_result_2 == 0:
            damage = 100
        else:
            return card.generate_response()

        packet : PacketType = [
            AVGECardHPChange(
                bench_target,
                damage,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.WOODWIND,
                ActionTypes.ATK_2,
                card,
            )
            for bench_target in opponent_bench if isinstance(bench_target, AVGECharacterCard)
        ]
        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_2, IzzyChen)))
        return card.generate_response()
