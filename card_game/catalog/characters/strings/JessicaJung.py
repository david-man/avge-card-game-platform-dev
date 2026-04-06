from __future__ import annotations

from random import randint

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class JessicaJung(AVGECharacterCard):
    _ACTIVE_USED_KEY = "jessicajung_active_used"
    _COIN_KEY = "jessicajung_coin"
    _SUPPORTER_SELECTION_KEY = "jessicajung_supporter_choice"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 1, 2)
        self.has_atk_1 = True
        self.atk_1_cost = 2
        self.has_atk_2 = False
        self.has_passive = False
        self.has_active = True

    @staticmethod
    def can_play_active(card: AVGECharacterCard) -> bool:
        used = card.env.cache.get(card, JessicaJung._ACTIVE_USED_KEY, None)
        return used != card.env.round_id

    @staticmethod
    def active(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, TransferCardCreator

        card.env.cache.set(card, JessicaJung._ACTIVE_USED_KEY, card.env.round_id)
        discard = card.player.cardholders[Pile.DISCARD]
        supporter_cards = [c for c in list(discard) if isinstance(c, AVGESupporterCard)]
        if len(supporter_cards) == 0:
            return card.generate_response()

        flip = card.env.cache.get(card, JessicaJung._COIN_KEY, None, True)
        if flip is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [JessicaJung._COIN_KEY],
                            InputType.COIN,
                            lambda r: True,
                            ActionTypes.ACTIVATE_ABILITY,
                            card,
                            {"query_label": "jessica_jung_active"},
                        )
                    ]
                },
            )

        if int(flip) != 1:
            return card.generate_response()

        chosen = card.env.cache.get(card, JessicaJung._SUPPORTER_SELECTION_KEY, None, True)
        if chosen is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [JessicaJung._SUPPORTER_SELECTION_KEY],
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ACTIVATE_ABILITY,
                            card,
                            {
                                "query_label": "jessica_jung_supporter",
                                "targets": supporter_cards,
                            },
                        )
                    ]
                },
            )

        deck = card.player.cardholders[Pile.DECK]
        card.propose(
            AVGEPacket([
                TransferCardCreator(chosen, discard, deck, ActionTypes.ACTIVATE_ABILITY, card, lambda: randint(0, len(deck)))
            ], AVGEEngineID(card, ActionTypes.ACTIVATE_ABILITY, JessicaJung))
        )
        return card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChangeCreator

        card.propose(
            AVGEPacket([
                AVGECardHPChangeCreator(
                    lambda: card.player.opponent.get_active_card(),
                    40,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.STRING,
                    ActionTypes.ATK_1,
                    card,
                )
            ], AVGEEngineID(card, ActionTypes.ATK_1, JessicaJung))
        )

        return card.generate_response()
