from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import TransferCard, PlayNonCharacterCard, AVGECardHPChange, AVGEEnergyTransfer


class IrisYang(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.STRING, 1, 3, 3)
        self.atk_1_name = 'Open Strings'
        self.atk_2_name = 'Spike'

    def atk_1(self, card: AVGECharacterCard) -> Response:
        def atk_active() -> PacketType:
            packet: PacketType = []
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        10,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.STRING,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )
            return packet

        packet: PacketType = [atk_active]

        deck = card.player.cardholders[Pile.DECK]
        hand = card.player.cardholders[Pile.HAND]
        discard = card.player.cardholders[Pile.DISCARD]

        def draw_and_maybe_use_item() -> PacketType:
            p: PacketType = []
            if len(deck) == 0:
                return p

            top = deck.peek()
            p.append(TransferCard(top, deck, hand, ActionTypes.ATK_1, card, None))
            if isinstance(top, AVGEItemCard):
                # Open Strings requires immediate item play after drawing.
                p.append(PlayNonCharacterCard(top, ActionTypes.ATK_1, card))
                p.append(TransferCard(top, hand, discard, ActionTypes.ATK_1, card, None))
            return p

        packet.append(draw_and_maybe_use_item)

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, IrisYang)))
        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard) -> Response:
        def generate_packet() -> PacketType:
            packet: PacketType = []
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        10,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.STRING,
                        ActionTypes.ATK_2,
                        None,
                        card,
                    )
                )

            for c in card.player.opponent.cardholders[Pile.BENCH]:
                if isinstance(c, AVGECharacterCard) and len(c.energy) >= 1:
                    packet.append(
                        AVGEEnergyTransfer(
                            c.energy[0],
                            c,
                            c.env,
                            ActionTypes.ATK_2,
                            card,
                            None,
                        )
                    )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_2, IrisYang)))
        return self.generic_response(card, ActionTypes.ATK_2)
