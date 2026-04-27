from __future__ import annotations

import random

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import AVGECardHPChange, TransferCard, EmptyEvent, PlayCharacterCard


class DavidMan(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.PIANO, 2, 3)
        self.atk_1_name = 'Three Hand Technique'
        self.active_name = 'Reverse Heist'

    def can_play_active(self) -> bool:
        if self.env.player_turn != self.player:
            return False

        discard = self.player.cardholders[Pile.DISCARD]
        if len(discard) == 0:
            return False

        _, already_used_idx = self.env.check_history(
            self.env.round_id,
            PlayCharacterCard,
            {
                'card': self,
                'card_action': ActionTypes.ACTIVATE_ABILITY,
                'caller': self,
            },
        )
        return already_used_idx == -1

    def active(self) -> Response:
        discard = self.player.cardholders[Pile.DISCARD]
        deck = self.player.cardholders[Pile.DECK]
        if len(discard) == 0:
            return Response(ResponseType.CORE, Data())

        chosen_card = random.choice(list(discard))

        def generate_packet() -> PacketType:
            packet: PacketType = []
            if not isinstance(chosen_card, AVGECard) or chosen_card not in discard:
                return packet

            packet.append(
                EmptyEvent(
                    ActionTypes.ACTIVATE_ABILITY,
                    self,
                    ResponseType.CORE,
                    RevealCards(
                        'Reverse Heist: Randomly selected discard card',
                        [self.player.unique_id],
                        default_timeout,
                        [chosen_card],
                    ),
                )
            )
            packet.append(
                TransferCard(
                    chosen_card,
                    discard,
                    deck,
                    ActionTypes.ACTIVATE_ABILITY,
                    self,
                    None,
                    random.randint(0, len(deck)),
                )
            )
            return packet

        self.propose(AVGEPacket([generate_packet], AVGEEngineID(self, ActionTypes.ACTIVATE_ABILITY, DavidMan)))
        return self.generic_response(self, ActionTypes.ACTIVATE_ABILITY)

    def atk_1(self, card: AVGECharacterCard) -> Response:
        def make_hit():
            def hit() -> PacketType:
                packet: PacketType = []
                active = card.player.opponent.get_active_card()
                if isinstance(active, AVGECharacterCard):
                    packet.append(
                        AVGECardHPChange(
                            active,
                            20,
                            AVGEAttributeModifier.SUBSTRACTIVE,
                            CardType.PIANO,
                            ActionTypes.ATK_1,
                            None,
                            card,
                        )
                    )
                return packet

            return hit
        for _ in range(3):
            card.propose(
                AVGEPacket([
                    make_hit()
                ], AVGEEngineID(card, ActionTypes.ATK_1, DavidMan))
            )

        return self.generic_response(card, ActionTypes.ATK_1)
