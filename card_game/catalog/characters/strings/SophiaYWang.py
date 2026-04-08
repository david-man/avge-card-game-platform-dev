from __future__ import annotations

from random import randint

from card_game.avge_abstracts import *
from card_game.catalog.items.AVGEBirb import AVGEBirb
from card_game.constants import *
from card_game.constants import ActionTypes

class SophiaYWang(AVGECharacterCard):
    _GACHA_GAMING_DRAW_KEY = "sophiaywang_gacha_gaming_draw"
    _GACHA_GAMING_DRAWN_CARDS = "sophiaywang_gacha_gaming_cards_drawn"
    _ENERGY_REMOVAL_KEY = "sophiaywang_energy_removal"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 1, 1, 3)
        self.has_atk_1 = True
        self.atk_1_cost = 1
        self.has_atk_2 = True
        self.atk_2_cost = 3
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange, InputEvent, TransferCard

        env = card.env

        deck = card.player.cardholders[Pile.DECK]
        current_cards= env.cache.get(card, SophiaYWang._GACHA_GAMING_DRAWN_CARDS, [], True)
        assert isinstance(current_cards, list)
        if len(deck) == 0 or card.hp < 20:
            for transferred_card in current_cards:
                assert isinstance(transferred_card, AVGECard)
                def put_back(c=transferred_card) -> PacketType:
                    return [
                        TransferCard(
                            c,
                            c.cardholder,
                            card.player.cardholders[Pile.DECK],
                            ActionTypes.ATK_1,
                            card,
                            randint(0, len(deck)),
                        )
                    ]
                card.propose(
                    AVGEPacket([
                        put_back
                    ], AVGEEngineID(card, ActionTypes.ATK_1, SophiaYWang))
                )
            return card.generate_response()

        draw = env.cache.get(card, SophiaYWang._GACHA_GAMING_DRAW_KEY, None, True)
        if draw is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [SophiaYWang._GACHA_GAMING_DRAW_KEY],
                            InputType.BINARY,
                            lambda l: True,
                            ActionTypes.ATK_1,
                            card,
                            {"query_label": "sophia_y_wang_gacha_gaming_draw_next"},
                        )
                    ]
                },
            )

        if draw:
            next_card = deck.peek()
            if isinstance(next_card, AVGEBirb):
                card.propose(
                    AVGEPacket([
                        AVGECardHPChange(
                            card,
                            card.max_hp,
                            AVGEAttributeModifier.SET_STATE,
                            card.card_type,
                            ActionTypes.ATK_1,
                            card,
                        )
                    ], AVGEEngineID(card, ActionTypes.ATK_1, SophiaYWang))
                )
                card.propose(
                    AVGEPacket([
                        TransferCard(next_card, deck, card.player.cardholders[Pile.HAND], ActionTypes.ATK_1, card)
                    ], AVGEEngineID(card, ActionTypes.ATK_1, SophiaYWang))
                )
                env.cache.set(card, SophiaYWang._GACHA_GAMING_DRAWN_CARDS, [])
                return card.generate_response()
            env.cache.set(card, SophiaYWang._GACHA_GAMING_DRAWN_CARDS, current_cards + [next_card])
            card.propose(
                AVGEPacket([
                    TransferCard(next_card, deck, card.player.cardholders[Pile.HAND], ActionTypes.ATK_1, card)
                ], AVGEEngineID(card, ActionTypes.ATK_1, SophiaYWang))
            )
            card.propose(
                AVGEPacket([
                    AVGECardHPChange(
                        card,
                        20,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        card.card_type,
                        ActionTypes.ATK_1,
                        card,
                    )
                ], AVGEEngineID(card, ActionTypes.ATK_1, SophiaYWang))
            )
            return card.generate_response()

        for transferred_card in current_cards:
            assert isinstance(transferred_card, AVGECard)
            def put_back(c=transferred_card) -> PacketType:
                return [
                    TransferCard(
                        c,
                        c.cardholder,
                        card.player.cardholders[Pile.DECK],
                        ActionTypes.ATK_1,
                        card,
                        randint(0, len(deck)),
                    )
                ]
            card.propose(
                AVGEPacket([
                    put_back
                ], AVGEEngineID(card, ActionTypes.ATK_1, SophiaYWang))
            )
        env.cache.set(card, SophiaYWang._GACHA_GAMING_DRAWN_CARDS, [])
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange, AVGEEnergyTransfer, EmptyEvent, InputEvent

        opponent = card.player.opponent

        chosen_target = card.env.cache.get(card, SophiaYWang._ENERGY_REMOVAL_KEY, None, True)
        if chosen_target is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [SophiaYWang._ENERGY_REMOVAL_KEY],
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            {
                                "query_label": "sophia_y_wang_atk_2",
                                "targets": opponent.get_cards_in_play(),
                                "display": opponent.get_cards_in_play()
                            },
                        )
                    ]
                },
            )

        packet = [] + [
            AVGECardHPChange(
                opponent.get_active_card(),
                20,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.STRING,
                ActionTypes.ATK_2,
                card,
            )
        ]
        assert isinstance(chosen_target, AVGECharacterCard)
        if len(chosen_target.energy) == 0:
            packet.append(
                EmptyEvent(
                    ActionTypes.ATK_2,
                    card,
                    response_data={MESSAGE_KEY: "SophiaYWang ATK2 target has no energy to discard."},
                )
            )
        else:
            for token in list(chosen_target.energy)[:2]:
                packet.append(AVGEEnergyTransfer(token, chosen_target, chosen_target.env, ActionTypes.ATK_2, card))

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_2, SophiaYWang)))
        return card.generate_response()