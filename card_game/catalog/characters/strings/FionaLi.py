from __future__ import annotations

from card_game.avge_abstracts import *

from card_game.constants import *
from card_game.engine.engine_constants import *


class FionaLi(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.STRING, 1, 1)
        self.has_atk_1 = True
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardStatusChange, TransferCard
        owner_card = card

        class _BenchMaidReactor(AVGEReactor):
            def __init__(self):
                super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, FionaLi), group=EngineGroup.EXTERNAL_REACTORS)
                self.owner_card = owner_card

            def update_status(self):
                return

            def event_match(self, event):
                if self.owner_card.cardholder is None or self.owner_card.cardholder.pile_type != Pile.BENCH:
                    return False
                if not isinstance(event, TransferCard):
                    return False
                if event.pile_from.pile_type == Pile.ACTIVE and event.pile_from.player == self.owner_card.player:
                    return isinstance(event.card, AVGECharacterCard)
                if event.pile_to.pile_type == Pile.ACTIVE and event.pile_to.player == self.owner_card.player:
                    return isinstance(event.card, AVGECharacterCard)
                return False

            def react(self, args=None) -> Response:
                if args is None:
                    args = {}
                event = self.attached_event
                assert isinstance(event, TransferCard)

                if event.pile_from.pile_type == Pile.ACTIVE and event.pile_from.player == self.owner_card.player:
                    if isinstance(event.card, AVGECharacterCard):
                        self.owner_card.propose(
                            AVGEPacket([
                                AVGECardStatusChange(StatusEffect.MAID, StatusChangeType.ERASE, event.card, ActionTypes.NONCHAR, self.owner_card)
                            ], AVGEEngineID(self.owner_card, ActionTypes.NONCHAR, FionaLi))
                        )
                        return self.generate_response()

                if event.pile_to.pile_type == Pile.ACTIVE and event.pile_to.player == self.owner_card.player:
                    if isinstance(event.card, AVGECharacterCard):
                        self.owner_card.propose(
                            AVGEPacket([
                                AVGECardStatusChange(StatusEffect.MAID, StatusChangeType.ADD, event.card, ActionTypes.NONCHAR, self.owner_card)
                            ], AVGEEngineID(self.owner_card, ActionTypes.NONCHAR, FionaLi))
                        )
                        return self.generate_response()

                return self.generate_response()

        if owner_card.cardholder.pile_type == Pile.BENCH:
            active = owner_card.player.get_active_card()
            print("FIONALI: ACTIVE: ", active.unique_id)
            if isinstance(active, AVGECharacterCard):
                owner_card.propose(
                    AVGEPacket([
                        AVGECardStatusChange(StatusEffect.MAID, StatusChangeType.ADD, active, ActionTypes.PASSIVE, owner_card)
                    ], AVGEEngineID(owner_card, ActionTypes.PASSIVE, FionaLi))
                )

        owner_card.add_listener(_BenchMaidReactor())
        return owner_card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        def generate_packet() -> PacketType:
            active = card.player.opponent.get_active_card()
            if not isinstance(active, AVGECharacterCard):
                return []
            return [
                AVGECardHPChange(
                    active,
                    40,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.STRING,
                    ActionTypes.ATK_1,
                    card,
                )
            ]

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, FionaLi)))

        return card.generate_response()
