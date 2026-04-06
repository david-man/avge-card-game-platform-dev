from __future__ import annotations

from card_game.avge_abstracts.AVGECards import *
from card_game.avge_abstracts.AVGEEventListeners import AVGEModifier
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class _RobertoGuitarBoost(AVGEModifier):
    def __init__(self, owner_card: AVGECharacterCard, round_active: int):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.NONCHAR, RobertoGonzales), group=EngineGroup.EXTERNAL_MODIFIERS_2)
        self.owner_card = owner_card
        self.round_active = round_active

    def event_match(self, event):
        from card_game.internal_events import AVGECardHPChange

        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if not isinstance(event.caller_card, AVGECharacterCard):
            return False
        if event.caller_card.player != self.owner_card.player:
            return False
        if event.change_type != CardType.GUITAR:
            return False
        if self.owner_card.env.round_id != self.round_active:
            return False
        return True

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        if self.owner_card.env.round_id > self.round_active:
            self.invalidate()

    def make_announcement(self) -> bool:
        return True

    def package(self):
        return "Roberto Gonzales Guitar Boost Modifier"

    def modify(self, args=None):
        if args is None:
            args = {}
        from card_game.internal_events import AVGECardHPChange

        event = self.attached_event
        assert isinstance(event, AVGECardHPChange)
        event.modify_magnitude(40)
        return self.generate_response()


class RobertoGonzales(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.GUITAR, 2, 2, 3)
        self.has_atk_1 = True
        self.atk_1_cost = 2
        self.has_atk_2 = True
        self.atk_2_cost = 3
        self.has_passive = False
        self.has_active = False

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange, TransferCardCreator, AVGEEnergyTransfer

        opponent = card.player.opponent

        def generate_packet():
            packet = []
            packet.append(
                AVGECardHPChange(
                    opponent.get_active_card(),
                    30,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.GUITAR,
                    ActionTypes.ATK_1,
                    card,
                )
            )

            current_energy = len(card.energy)
            for token in list(card.energy):
                packet.append(AVGEEnergyTransfer(token, card, card.player, ActionTypes.ATK_1, card))

            deck = opponent.cardholders[Pile.DECK]
            discard = opponent.cardholders[Pile.DISCARD]
            for _ in range(min(current_energy, len(deck))):
                packet.append(TransferCardCreator(lambda: deck.peek(), deck, discard, ActionTypes.ATK_1, card))
            return packet

        card.propose(AVGEPacket(generate_packet, AVGEEngineID(card, ActionTypes.ATK_1, RobertoGonzales)))
        return card.generate_response()

    @staticmethod
    def atk_2(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChangeCreator

        card.propose(
            AVGEPacket([
                AVGECardHPChangeCreator(
                    lambda: card.player.opponent.get_active_card(),
                    40,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.GUITAR,
                    ActionTypes.ATK_2,
                    card,
                )
            ], AVGEEngineID(card, ActionTypes.ATK_2, RobertoGonzales))
        )
        card.add_listener(_RobertoGuitarBoost(card, card.player.get_next_turn()))

        return card.generate_response()
