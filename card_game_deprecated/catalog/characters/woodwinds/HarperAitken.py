from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import AVGECardHPChange, InputEvent

class HarperAitken(AVGECharacterCard):
    _TARGET_1_SELECTION_KEY = 'harperaitken_target_1_selection'
    _TARGET_2_SELECTION_KEY = 'harperaitken_target_2_selection'

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.WOODWIND, 2, 2, 3)
        self.atk_1_name = 'Overblow'
        self.atk_2_name = 'Wipeout'

    def atk_1(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        def gen() -> PacketType:
            packet: PacketType = []
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        50,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.WOODWIND,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )
            packet.append(
                AVGECardHPChange(
                    card,
                    10,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_1,
                    None,
                    card,
                )
            )
            return packet

        card.propose(AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_1, HarperAitken)))
        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        opponent = card.player.opponent
        chars_in_play = [c for c in opponent.get_cards_in_play() if isinstance(c, AVGECharacterCard)]

        missing = object()
        target_1 = card.env.cache.get(card, HarperAitken._TARGET_1_SELECTION_KEY, missing, True)
        target_2 = card.env.cache.get(card, HarperAitken._TARGET_2_SELECTION_KEY, missing, True)
        if target_1 is missing:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [HarperAitken._TARGET_1_SELECTION_KEY, HarperAitken._TARGET_2_SELECTION_KEY],
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            CardSelectionQuery(
                                'Wipeout: Choose up to two different targets in opponent\'s play area.',
                                chars_in_play,
                                chars_in_play,
                                True,
                                False,
                            )
                        )
                    ]),
            )

        def generate_packet() -> PacketType:
            packet: PacketType = []
            if(isinstance(target_1, AVGECharacterCard)):
                packet.append(AVGECardHPChange(
                    target_1,
                    80,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_2,
                    None,
                    card,
                ))
            if(isinstance(target_2, AVGECharacterCard)):
                packet.append(AVGECardHPChange(
                    target_2,
                    80,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_2,
                    None,
                    card,
                ))
            packet.append(AVGECardHPChange(
                    card,
                    80,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_2,
                    None,
                    card,
                ))
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_2, HarperAitken)))
        return self.generic_response(card, ActionTypes.ATK_2)
