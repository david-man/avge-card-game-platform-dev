from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *


class MasonYu(AVGECharacterCard):
    _ATK1_TARGET = "mason_atk1_target"
    _ATK2_COIN_BASE = "mason_atk2_coin_"
    _ATK2_TARGET_1 = "mason_atk2_target_1"
    _ATK2_TARGET_2 = "mason_atk2_target_2"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 2, 1, 3)
        self.has_atk_1 = True
        self.atk_1_cost = 1
        self.has_atk_2 = True
        self.atk_2_cost = 3
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import AVGEEnergyTransfer, InputEvent

        player = card.player
        if len(player.energy) <= 0:
            return card.generate_response()

        bench = player.cardholders[Pile.BENCH]
        if len(bench) == 0:
            return card.generate_response()

        chosen = card.env.cache.get(card, MasonYu._ATK1_TARGET, None, True)
        if chosen is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            player,
                            [MasonYu._ATK1_TARGET],
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            {
                                "query_label": "mason_yu_atk1",
                                "targets": bench,
                            },
                        )
                    ]
                },
            )

        card.propose(AVGEEnergyTransfer(player.energy[0], player, chosen, ActionTypes.ATK_1, card))

        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import AVGEStatusChange, AVGECardHPChange, InputEvent
        from card_game.constants import StatusChangeType, StatusEffect

        player = card.player
        already_arranger = [c for c in player.get_cards_in_play() if int(c.statuses_attached.get(StatusEffect.ARRANGER, 0)) > 0]
        packet = []
        for c in player.get_cards_in_play():
            packet.append(AVGEStatusChange(c, StatusEffect.ARRANGER, StatusChangeType.ADD, ActionTypes.ATK_2, card))

        if len(already_arranger) == 0:
            card.propose(packet)
            return card.generate_response()

        coin_keys = [MasonYu._ATK2_COIN_BASE + str(i) for i in range(len(already_arranger))]
        rolls = [card.env.cache.get(card, key, None, True) for key in coin_keys]
        if rolls[0] is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            player,
                            coin_keys,
                            InputType.COIN,
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            {"query_label": "mason_yu_coinflips"},
                        )
                    ]
                },
            )

        heads = sum(rolls)

        if heads < 2:
            card.propose(packet)
            return card.generate_response()

        opp_cards = player.opponent.get_cards_in_play()
        if len(opp_cards) == 1:
            packet.append(
                AVGECardHPChange(
                    player.opponent.get_active_card(),
                    50,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.STRING,
                    ActionTypes.ATK_2,
                    card,
                )
            )
            packet.append(
                AVGECardHPChange(
                    player.opponent.get_active_card(),
                    50,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.STRING,
                    ActionTypes.ATK_2,
                    card,
                )
            )
            card.propose(packet)
            return card.generate_response()

        chosen_1 = card.env.cache.get(card, MasonYu._ATK2_TARGET_1, None, True)
        chosen_2 = card.env.cache.get(card, MasonYu._ATK2_TARGET_2, None, True)
        if chosen_1 is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            player,
                            [MasonYu._ATK2_TARGET_1, MasonYu._ATK2_TARGET_2],
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            {
                                "query_label": "mason_yu_atk_2_choice",
                                "targets": opp_cards,
                            },
                        )
                    ]
                },
            )
        packet.append(
            AVGECardHPChange(
                chosen_1,
                50,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.STRING,
                ActionTypes.ATK_2,
                card,
            )
        )
        packet.append(
            AVGECardHPChange(
                chosen_2,
                50,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.STRING,
                ActionTypes.ATK_2,
                card,
            )
        )
        card.propose(packet)

        return card.generate_response()
