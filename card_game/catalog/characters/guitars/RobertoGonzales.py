from __future__ import annotations

from card_game.avge_abstracts import *
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
        if not isinstance(event.caller, AVGECharacterCard):
            return False
        if event.caller.player != self.owner_card.player:
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

    def modify(self):
        from card_game.internal_events import AVGECardHPChange

        event = self.attached_event
        assert isinstance(event, AVGECardHPChange)
        event.modify_magnitude(40)
        return Response(ResponseType.ACCEPT, Notify("Distortion: +40 damage!", all_players, default_timeout))


class RobertoGonzales(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.GUITAR, 2, 2, 3)
        self.atk_1_name = 'Guitar Shredding'
        self.atk_2_name = 'Distortion'

    def atk_1(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        from card_game.internal_events import AVGECardHPChange, TransferCard, AVGEEnergyTransfer

        opponent = card.player.opponent
        def gen() -> PacketType:
            packet : PacketType= []
            packet += [AVGECardHPChange(
                    opponent.get_active_card(),
                    30,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.GUITAR,
                    ActionTypes.ATK_1,
                    None,
                    card,
                )]
            current_energy = len(card.energy)
            for token in list(card.energy):
                packet.append(AVGEEnergyTransfer(token, card, card.env, ActionTypes.ATK_1, card, None))
            deck = opponent.cardholders[Pile.DECK]
            discard = opponent.cardholders[Pile.DISCARD]
            def transfer_gen() -> PacketType:
                p: PacketType = []
                p.append(TransferCard(deck.peek(), deck, discard, ActionTypes.ATK_1, card, None))
                return p
            for _ in range(min(current_energy, len(deck))):
                packet.append(transfer_gen)
            return packet

        card.propose(AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_1, RobertoGonzales)))
        return self.generic_response(card, ActionTypes.ATK_1)

    def atk_2(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        from card_game.internal_events import AVGECardHPChange
        def gen() -> PacketType:
            packet: PacketType = []
            packet.append(
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    40,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.GUITAR,
                    ActionTypes.ATK_2,
                    None,
                    card,
                )
            )
            return packet
        card.propose(
            AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_2, RobertoGonzales))
        )
        card.add_listener(_RobertoGuitarBoost(card, card.player.get_next_turn()))

        return self.generic_response(card, ActionTypes.ATK_2)
