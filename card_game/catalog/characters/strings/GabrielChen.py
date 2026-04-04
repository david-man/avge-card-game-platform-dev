from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *


class GabrielChen(AVGECharacterCard):
    _COIN_KEY_0 = "gabrielchen_coin_0"
    _COIN_KEY_1 = "gabrielchen_coin_1"
    _ATK1_SELECTION_KEY = "gabrielchen_atk1_target"
    _ATK2_SELECTION_BASE_KEY = "gabrielchen_atk2_targets"
    _ATK2_MODE_KEY = "gabrielchen_atk2_mode"

    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.STRING, 1, 1, 2)
        self.has_atk_1 = True
        self.atk_1_cost = 1
        self.has_atk_2 = True
        self.atk_2_cost = 2
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import InputEvent, AVGECardHPChange

        if card.hp != 60:
            return card.generate_response()

        chosen = card.env.cache.get(card, GabrielChen._ATK1_SELECTION_KEY, None, True)
        if chosen is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [GabrielChen._ATK1_SELECTION_KEY],
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            {
                                "query_label": "gabe_chen_ykwis",
                                "targets": card.player.opponent.get_cards_in_play(),
                            },
                        )
                    ]
                },
            )

        card.propose(
            AVGECardHPChange(
                chosen,
                70,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.STRING,
                ActionTypes.ATK_1,
                card,
            )
        )

        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import InputEvent, AVGECardHPChange

        r0 = card.env.cache.get(card, GabrielChen._COIN_KEY_0, None, True)
        r1 = card.env.cache.get(card, GabrielChen._COIN_KEY_1, None, True)
        if r0 is None or r1 is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [GabrielChen._COIN_KEY_0, GabrielChen._COIN_KEY_1],
                            InputType.COIN,
                            lambda res: True,
                            ActionTypes.ATK_2,
                            card,
                            {"query_label": "gabe_harmonics_2coin"},
                        )
                    ]
                },
            )

        heads = int(r0) + int(r1)
        if heads != 2:
            return card.generate_response()

        mode = card.env.cache.get(card, GabrielChen._ATK2_MODE_KEY, None, True)
        if mode is None:
            def _mode_valid(res) -> bool:
                return len(res) == 1 and res[0] in ("three60", "two70")

            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [GabrielChen._ATK2_MODE_KEY],
                            InputType.DETERMINISTIC,
                            _mode_valid,
                            ActionTypes.ATK_2,
                            card,
                            {"query_label": "gabe_harmonics_mode_choice"},
                        )
                    ]
                },
            )

        req_count = 3 if mode == "three60" else 2
        count = min(req_count, len(card.player.opponent.get_cards_in_play()))
        keys = [GabrielChen._ATK2_SELECTION_BASE_KEY + str(i) for i in range(count)]
        chosen = [card.env.cache.get(card, key, None, True) for key in keys]
        if chosen[0] is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            keys,
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            {
                                "query_label": "gabe_harmonics",
                                "targets": card.player.opponent.get_cards_in_play(),
                                "allow_repeats": False,
                            },
                        )
                    ]
                },
            )

        dmg_amt = 60 if mode == "three60" else 70
        for tgt in chosen:
            card.propose(
                AVGECardHPChange(
                    tgt,
                    dmg_amt,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.STRING,
                    ActionTypes.ATK_2,
                    card,
                )
            )
        return card.generate_response()
