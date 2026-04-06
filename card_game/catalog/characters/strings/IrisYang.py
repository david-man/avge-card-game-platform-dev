from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.constants import *


class IrisYang(AVGECharacterCard):
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
        from card_game.internal_events import TransferCard, PlayNonCharacterCard, AVGECardHPChange

        packet = [] + [
            AVGECardHPChange(
                card.player.opponent.get_active_card(),
                10,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.STRING,
                ActionTypes.ATK_1,
                card,
            )
        ]

        deck = card.player.cardholders[Pile.DECK]
        hand = card.player.cardholders[Pile.HAND]
        discard = card.player.cardholders[Pile.DISCARD]

        if len(deck) == 0:
            card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, IrisYang)))
            return card.generate_response()

        top = deck.peek()
        if isinstance(top, AVGEItemCard):
            packet.append(TransferCard(top, deck, hand, ActionTypes.ATK_1, card))
            packet.append(PlayNonCharacterCard(top, ActionTypes.ATK_1, card))
            packet.append(TransferCard(top, hand, discard, ActionTypes.ATK_1, card))
        else:
            packet.append(TransferCard(top, deck, hand, ActionTypes.ATK_1, card))

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, IrisYang)))
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange, AVGEEnergyTransfer

        packet = [] + [
            AVGECardHPChange(
                card.player.opponent.get_active_card(),
                10,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.STRING,
                ActionTypes.ATK_2,
                card,
            )
        ]
        for c in card.player.opponent.cardholders[Pile.BENCH]:
            assert isinstance(c, AVGECharacterCard)
            if len(c.energy) >= 1:
                packet.append(AVGEEnergyTransfer(c.energy[0], c, c.player, ActionTypes.ATK_2, card))

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_2, IrisYang)))
        return card.generate_response()
