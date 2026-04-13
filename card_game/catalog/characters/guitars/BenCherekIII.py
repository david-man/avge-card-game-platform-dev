from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import InputEvent, TransferCard

class BenCherekIII(AVGECharacterCard):
    _YES_NO_KEY = "bencherek_yn_key"

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.GUITAR, 2, 2)
        self.has_atk_1 = True
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard) -> Response:
        yn = card.env.cache.get(card, BenCherekIII._YES_NO_KEY, None, True)
        if yn is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [BenCherekIII._YES_NO_KEY],
                            InputType.BINARY,
                            lambda r: True,
                            ActionTypes.PASSIVE,
                            card,
                            {LABEL_FLAG: "ben_cherek_yn_key"},
                        )
                    ]
                },
            )
        if yn:
            def gen() -> PacketType:
                return [TransferCard(
                    card,
                    card.cardholder,
                    card.player.cardholders[Pile.ACTIVE],
                    ActionTypes.PASSIVE,
                    card,
                ),
                TransferCard(
                    card.player.get_active_card(),
                    card.player.cardholders[Pile.ACTIVE],
                    card.player.cardholders[Pile.BENCH],
                    ActionTypes.PASSIVE,
                    card,
                )]
            card.propose(AVGEPacket([
                gen,
            ], AVGEEngineID(card, ActionTypes.PASSIVE, BenCherekIII)))
        return card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        packet : PacketType= []
        def gen() -> PacketType:
            return [AVGECardHPChange(
                card.player.opponent.get_active_card(),
                50,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.GUITAR,
                ActionTypes.ATK_1,
                card,
            )]
        packet.append(gen)

        for c in card.player.cardholders[Pile.BENCH]:
            assert isinstance(c, AVGECharacterCard)
            if c.card_type == CardType.GUITAR:
                packet.append(
                    AVGECardHPChange(
                        c,
                        10,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.GUITAR,
                        ActionTypes.ATK_1,
                        card,
                    )
                )

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, BenCherekIII)))
        return card.generate_response()
