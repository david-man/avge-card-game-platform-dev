from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.internal_events import InputEvent, TransferCard

class BenCherekIII(AVGECharacterCard):
    _YES_NO_KEY = "bencherek_yn_key"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.GUITAR, 1, 2)
        self.atk_1_name = 'Feedback Loop'
        self.has_passive = True

    def passive(self) -> Response:
        if self.cardholder is None or self.cardholder.pile_type != Pile.BENCH:
            return Response(ResponseType.CORE, Data())
        if len(self.player.cardholders[Pile.ACTIVE]) == 0:
            return Response(ResponseType.CORE, Data())
        _, played_from_hand_to_bench_idx = self.env.check_history(
            self.env.round_id,
            TransferCard,
            {
                'card': self,
                'pile_from': self.player.cardholders[Pile.HAND],
                'pile_to': self.player.cardholders[Pile.BENCH],
            },
        )
        if played_from_hand_to_bench_idx != -1:
            return Response(ResponseType.CORE, Data())

        yn = self.env.cache.get(self, BenCherekIII._YES_NO_KEY, None, True)
        if yn is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            self.player,
                            [BenCherekIII._YES_NO_KEY],
                            lambda r: True,
                            ActionTypes.PASSIVE,
                            self,
                            StrSelectionQuery("Loudmouth: Do you want to immediately set Ben Cherek as active?",
                                              ["Yes", "No"],
                                              ["Yes", "No"],
                                              False,
                                              False)
                        )
                    ]),
            )
        if yn in [True, "Yes"]:
            def gen() -> PacketType:
                return [TransferCard(
                    self,
                    self.cardholder,
                    self.player.cardholders[Pile.ACTIVE],
                    ActionTypes.PASSIVE,
                    self,
                    None,
                ),
                TransferCard(
                    self.player.get_active_card(),
                    self.player.cardholders[Pile.ACTIVE],
                    self.player.cardholders[Pile.BENCH],
                    ActionTypes.PASSIVE,
                    self,
                    None,
                )]
            self.propose(AVGEPacket([
                gen,
            ], AVGEEngineID(self, ActionTypes.PASSIVE, BenCherekIII)))
        return Response(ResponseType.CORE, Data())

    def atk_1(self, card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        packet : PacketType= []
        def gen() -> PacketType:
            return [AVGECardHPChange(
                card.player.opponent.get_active_card(),
                50,
                AVGEAttributeModifier.SUBSTRACTIVE,
                CardType.GUITAR,
                ActionTypes.ATK_1,
                None,
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
                        None,
                        card,
                    )
                )

        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, BenCherekIII)))
        return self.generic_response(card, ActionTypes.ATK_1)
