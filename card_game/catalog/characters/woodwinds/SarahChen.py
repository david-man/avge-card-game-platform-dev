from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.catalog.items.ConcertProgram import ConcertProgram
from card_game.catalog.items.ConcertTicket import ConcertTicket


class SarahChen(AVGECharacterCard):
    _DISCARD_SELECTION_KEY = "sarah_discard_selection"
    _TARGET_SELECTION_KEY = "sarah_target_selection"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.WOODWIND, 1, 1, 3)
        self.has_atk_1 = True
        self.has_atk_2 = True
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange
        def gen() -> PacketType:
            return [
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    10,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.WOODWIND,
                    ActionTypes.ATK_1,
                    card,
                )
            ]
        card.propose(
            AVGEPacket([gen for _ in range(2)], AVGEEngineID(card, ActionTypes.ATK_1, SarahChen))
        )
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange, InputEvent, TransferCard

        player = card.player
        hand = player.cardholders[Pile.HAND]
        discard = player.cardholders[Pile.DISCARD]
        opponent = card.player.opponent

        eligible_cards = [
            hand_card
            for hand_card in hand
            if isinstance(hand_card, (ConcertProgram, ConcertTicket))
        ]
        if len(eligible_cards) == 0:
            return card.generate_response(data={MESSAGE_KEY: "No concert programs or tickets in hand!"})

        discard_keys = [SarahChen._DISCARD_SELECTION_KEY + str(i) for i in range(len(eligible_cards))]
        missing = object()
        discard_vals = [card.env.cache.get(card, key, missing) for key in discard_keys]
        if discard_vals[0] is missing:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            player,
                            discard_keys,
                            InputType.SELECTION,
                            lambda r: True,
                            ActionTypes.ATK_2,
                            card,
                            {
                                LABEL_FLAG: "sarah_chen_atk_2_discard",
                                TARGETS_FLAG: eligible_cards,
                                DISPLAY_FLAG: list(hand),
                                ALLOW_NONE: True
                            },
                        )
                    ]
                },
            )
        packet : PacketType = []
        selected_keys = []
        for i in range(len(discard_vals)):
            if(discard_vals[i] is not None):
                selected_keys.append(SarahChen._TARGET_SELECTION_KEY + str(i))
        if(len(selected_keys) > 0):
            targets_vals = [card.env.cache.get(card, key, missing, True) for key in selected_keys]
            if targets_vals[0] is missing:
                return card.generate_response(
                    ResponseType.INTERRUPT,
                    {
                        INTERRUPT_KEY: [
                            InputEvent(
                                player,
                                selected_keys,
                                InputType.SELECTION,
                                lambda r: True,
                                ActionTypes.ATK_2,
                                card,
                                {
                                    LABEL_FLAG: "sarah_chen_atk_2_target",
                                    TARGETS_FLAG: opponent.get_cards_in_play(),
                                    DISPLAY_FLAG: opponent.get_cards_in_play(),
                                    ALLOW_REPEAT: True
                                },
                            )
                        ]
                    },
                )
            
            for target in targets_vals:
                assert isinstance(target, AVGECharacterCard)
                packet.append(AVGECardHPChange(
                            target,
                            40,
                            AVGEAttributeModifier.SUBSTRACTIVE,
                            CardType.WOODWIND,
                            ActionTypes.ATK_2,
                            card,
                        ))
        for to_discard in discard_vals:
            if(to_discard is not None):
                assert isinstance(to_discard, AVGECard)
                packet.append(TransferCard(
                    to_discard,
                    to_discard.cardholder,
                    to_discard.player.cardholders[Pile.DISCARD],
                    ActionTypes.ATK_2,
                    card
                ))
        for key in discard_keys:
            card.env.cache.delete(card, key)
        if(len(packet) > 0):
            card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_2, SarahChen)))
        return card.generate_response()
