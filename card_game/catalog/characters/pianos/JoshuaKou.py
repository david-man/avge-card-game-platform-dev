from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import InputEvent, TransferCard, AVGECardHPChange, PlayCharacterCard

class JoshuaKou(AVGECharacterCard):
    _PASSIVE_DRAW_CHOICE_KEY = "joshuakou_passive_draw_choice"

    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.PIANO, 1, 1)
        self.atk_1_name = 'Separate Hands'
        self.has_passive = True

    def passive(self) -> Response:
        hand = self.player.cardholders[Pile.HAND]
        deck = self.player.cardholders[Pile.DECK]

        if len(hand) >= 4 or len(deck) == 0:
            return Response(ResponseType.CORE, Data())

        draw_choice = self.env.cache.get(self, JoshuaKou._PASSIVE_DRAW_CHOICE_KEY, None, True)
        if draw_choice is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            self.player,
                            [JoshuaKou._PASSIVE_DRAW_CHOICE_KEY],
                            lambda r: True,
                            ActionTypes.PASSIVE,
                            self,
                            StrSelectionQuery(
                                'Category Theory: Draw until you have four cards in hand?',
                                ['Yes', 'No'],
                                ['Yes', 'No'],
                                False,
                                False,
                            )
                        )
                    ]),
            )

        if draw_choice != 'Yes':
            return Response(ResponseType.CORE, Data())

        def draw_until_four() -> PacketType:
            current_hand = self.player.cardholders[Pile.HAND]
            current_deck = self.player.cardholders[Pile.DECK]
            draws = min(4 - len(current_hand), len(current_deck))
            packet: PacketType = []
            for _ in range(draws):
                packet.append(
                    TransferCard(
                        current_deck.peek(),
                        current_deck,
                        current_hand,
                        ActionTypes.PASSIVE,
                        self,
                        None,
                    )
                )
            return packet

        self.propose(
            AVGEPacket([
                draw_until_four
            ], AVGEEngineID(self, ActionTypes.PASSIVE, JoshuaKou))
        )
        return Response(ResponseType.CORE, Data())

    def atk_1(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
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
            def generate_packet() -> PacketType:
                active = card.player.opponent.get_active_card()
                packet: PacketType = []
                packet.append(
                    AVGECardHPChange(
                        active,
                        40,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.PIANO,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )
                return packet

            card.propose(
                AVGEPacket([
                    generate_packet
                ], AVGEEngineID(card, ActionTypes.ATK_1, JoshuaKou))
            )

        return self.generic_response(card, ActionTypes.ATK_1)
