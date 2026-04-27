from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import AVGECardHPChange, TransferCard, PlayCharacterCard, EmptyEvent

class HenryWang(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.PIANO, 2, 2, 3)
        self.atk_1_name = 'Glissando'
        self.atk_2_name = 'Improv'

    def atk_1(self, card: AVGECharacterCard) -> Response:
        _, used_last_turn_idx = card.env.check_history(
            card.player.get_last_turn(),
            PlayCharacterCard,
            {
                'card': card,
                'card_action': ActionTypes.ATK_1,
                'caller': card,
            },
        )
        if used_last_turn_idx != -1:
            return Response(
                ResponseType.CORE,
                Notify('Glissando cannot be used this turn.', [card.player.unique_id], default_timeout),
            )

        def gen() -> PacketType:
            packet: PacketType = []
            packet.append(
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    50,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PIANO,
                    ActionTypes.ATK_1,
                    None,
                    card,
                )
            )
            return packet

        card.propose(
            AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_1, HenryWang))
        )

        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard) -> Response:
        opponent = card.player.opponent

        def generate_packet() -> PacketType:
            deck = opponent.cardholders[Pile.DECK]
            discard = opponent.cardholders[Pile.DISCARD]

            damage = 10
            packet : PacketType = []
            if len(deck) > 0:
                top = deck.peek()
                packet.append(TransferCard(top, deck, discard, ActionTypes.ATK_2, card, None))
                if isinstance(top, AVGEItemCard):
                    damage = 100

            packet.append(
                AVGECardHPChange(
                    opponent.get_active_card(),
                    damage,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PIANO,
                    ActionTypes.ATK_2,
                    None,
                    card,
                ),
            )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_2, HenryWang)))
        return self.generic_response(card, ActionTypes.ATK_2)
