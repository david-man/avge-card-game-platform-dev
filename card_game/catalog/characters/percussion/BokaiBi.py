from __future__ import annotations

from card_game.avge_abstracts import *

from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class BokaiBi(AVGECharacterCard):
    _D6_KEY = "bokaibi_d6_roll"

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.PERCUSSION, 2, 2)
        self.has_atk_1 = True
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard) -> Response:
        class _BokaiTransferReactor(AVGEReactor):
            def __init__(self):
                super().__init__(
                    identifier=AVGEEngineID(card, ActionTypes.PASSIVE, BokaiBi),
                    group=EngineGroup.EXTERNAL_REACTORS,
                )

            def event_match(self, event):
                from card_game.internal_events import TransferCard

                if not isinstance(event, TransferCard):
                    return False
                if event.pile_from.pile_type != Pile.HAND or event.pile_to.pile_type != Pile.BENCH:
                    return False
                if event.card.player != card.player.opponent:
                    return False
                for c in card.player.get_cards_in_play():
                    if isinstance(c, AVGECharacterCard) and type(c) == type(event.card):
                        return True
                return False

            def event_effect(self) -> bool:
                return True

            def update_status(self):
                return

            def react(self, args=None) -> Response:
                if args is None:
                    args = {}
                from card_game.internal_events import AVGECardHPChange, TransferCard

                event = self.attached_event
                assert isinstance(event, TransferCard)
                assert isinstance(event.card, AVGECharacterCard)
                card.propose(
                    AVGEPacket([
                        AVGECardHPChange(
                            event.card,
                            60,
                            AVGEAttributeModifier.SUBSTRACTIVE,
                            CardType.PERCUSSION,
                            ActionTypes.PASSIVE,
                            card,
                        )
                    ], AVGEEngineID(card, ActionTypes.PASSIVE, BokaiBi))
                )

                return self.generate_response()

        card.add_listener(_BokaiTransferReactor())
        return card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, AVGECardHPChange

        roll = card.env.cache.get(card, BokaiBi._D6_KEY, None, True)
        if roll is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [BokaiBi._D6_KEY],
                            InputType.D6,
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            {"query_label": "bokai_bi_d6"},
                        )
                    ]
                },
            )
        val = int(roll)
        if val <= 4:
            def generate() -> PacketType:
                return [AVGECardHPChange(
                        card.player.opponent.get_active_card(),
                        70,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.PERCUSSION,
                        ActionTypes.ATK_1,
                        card,
                    )]
            card.propose(
                AVGEPacket([
                    generate
                ], AVGEEngineID(card, ActionTypes.ATK_1, BokaiBi))
            )

        return card.generate_response()
