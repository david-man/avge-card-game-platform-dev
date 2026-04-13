from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
import math


class SophiaNextAttackHalvedModifier(AVGEModifier):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.NONCHAR, SophiaSWang), group=EngineGroup.EXTERNAL_MODIFIERS_2)
        self.owner_card = owner_card

    def event_match(self, event):
        from card_game.internal_events import AVGECardHPChange

        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]:
            return False
        if(not isinstance(event.caller_card, AVGECharacterCard)):
            return False
        if event.change_type == CardType.ALL:
            return False
        return event.caller_card.player == self.owner_card.player.opponent

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def on_packet_completion(self):
        self.invalidate()

    def modify(self, args=None):
        if args is None:
            args = {}
        from card_game.internal_events import AVGECardHPChange

        event = self.attached_event
        assert isinstance(event, AVGECardHPChange)
        event.modify_magnitude(-math.floor(event.magnitude / 2))
        return self.generate_response()


class _SophiaEnergyReactor(AVGEReactor):
    _LAST_ENERGY_TURN_KEY = "sophiaswang_last_energy_turn"

    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, SophiaSWang), group=EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card

    def event_match(self, event):
        from card_game.internal_events import AVGEEnergyTransfer

        if not isinstance(event, AVGEEnergyTransfer):
            return False
        if event.target != self.owner_card:
            return False

        last = self.owner_card.env.cache.get(self.owner_card, _SophiaEnergyReactor._LAST_ENERGY_TURN_KEY, None)
        if last is not None and self.owner_card.env.round_id == last:
            return False
        return True

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return


    def react(self, args=None):
        if args is None:
            args = {}
        from card_game.internal_events import TransferCard, EmptyEvent

        owner = self.owner_card
        env = owner.env

        env.cache.set(owner, _SophiaEnergyReactor._LAST_ENERGY_TURN_KEY, env.round_id)

        opp = owner.player.opponent
        deck = opp.cardholders[Pile.DECK]
        discard = opp.cardholders[Pile.DISCARD]
        if len(deck) == 0:
            return self.generate_response(data={MESSAGE_KEY: "Opponent has nothing in their deck!"})

        def mill_top() -> PacketType:
            if len(deck) == 0:
                return []
            return [
                TransferCard(
                    deck.peek(),
                    deck,
                    discard,
                    ActionTypes.PASSIVE,
                    owner,
                )
            ]

        owner.propose(
            AVGEPacket([
                mill_top
            ], AVGEEngineID(owner, ActionTypes.PASSIVE, SophiaSWang))
        )
        return self.generate_response()


class SophiaSWang(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.PIANO, 2, 2)
        self.has_atk_1 = True
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard) -> Response:
        card.add_listener(_SophiaEnergyReactor(card))
        return card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        def generate_packet() -> PacketType:
            active = card.player.opponent.get_active_card()
            return [
                AVGECardHPChange(
                    active,
                    20,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PIANO,
                    ActionTypes.ATK_1,
                    card,
                )
            ]

        card.propose(
            AVGEPacket([
                generate_packet
            ], AVGEEngineID(card, ActionTypes.ATK_1, SophiaSWang))
        )

        card.add_listener(SophiaNextAttackHalvedModifier(card))

        return card.generate_response()
