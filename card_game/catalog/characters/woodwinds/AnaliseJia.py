from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import *
from card_game.constants import *


class AnaliseJia(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.WOODWIND, 1, 1, 3)
        self.has_atk_1 = True
        self.atk_1_cost = 1
        self.has_atk_2 = True
        self.atk_2_cost = 3
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import AVGECardHPChange

        card.propose(
            [
                AVGECardHPChange(
                    lambda: card.player.opponent.get_active_card(),
                    10,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_1,
                    card,
                ),
                AVGECardHPChange(
                    lambda: card.player.opponent.get_active_card(),
                    10,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_1,
                    card,
                ),
            ]
        )
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard, parent_event: AVGEEvent) -> Response:
        from card_game.internal_events import AVGECardHPChange, AVGEEnergyTransfer, EmptyEvent

        def packet():
            p = [
                AVGECardHPChange(
                    character,
                    30,
                    AVGEAttributeModifier.ADDITIVE,
                    character.card_type,
                    ActionTypes.ATK_2,
                    card,
                )
                for character in card.player.get_cards_in_play()
            ]
            if len(card.energy) == 0:
                p.append(EmptyEvent("AnaliseJia ATK2 had no attached energy to remove.", ActionTypes.ATK_2, card))
            else:
                p.append(AVGEEnergyTransfer(card.energy[0], card, card.player, ActionTypes.ATK_2, card))
            return p

        card.propose(packet)
        return card.generate_response()
