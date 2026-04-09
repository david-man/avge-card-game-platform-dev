from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.constants import ActionTypes
class IrisYang(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 1, 1, 3)
        self.has_atk_1 = True
        self.has_atk_2 = True
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import TransferCard, PlayNonCharacterCard, AVGECardHPChange, EmptyEvent

        def atk_active() -> PacketType:
            return [
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    10,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.STRING,
                    ActionTypes.ATK_1,
                    card,
                )
            ]
        packet : PacketType = [atk_active]

        deck = card.player.cardholders[Pile.DECK]
        hand = card.player.cardholders[Pile.HAND]
        discard = card.player.cardholders[Pile.DISCARD]

        if len(deck) == 0:
            packet.insert(0, EmptyEvent(ActionTypes.ATK_1, card, response_data={MESSAGE_KEY: "No cards in deck!"}))
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
                packet.append(AVGEEnergyTransfer(c.energy[0], c, c.env, ActionTypes.ATK_2, card))

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_2, IrisYang)))
        return card.generate_response()
