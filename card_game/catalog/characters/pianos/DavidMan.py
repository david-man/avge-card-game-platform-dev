from __future__ import annotations

import random
import math

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import InputEvent, TransferCard, EmptyEvent, AVGECardHPChange, PlayCharacterCard


class DavidNextAttackHalvedModifier(AVGEModifier):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.NONCHAR, DavidMan), group=EngineGroup.EXTERNAL_MODIFIERS_2)
        self.owner_card = owner_card

    def event_match(self, event):
        from card_game.internal_events import AVGECardHPChange

        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if event.change_type == CardType.ALL:
            return False
        if event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]:
            return False
        if(not isinstance(event.caller, AVGECharacterCard)):
            return False
        return event.caller.player == self.owner_card.player.opponent

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def on_packet_completion(self):
        self.invalidate()

    def modify(self, args=None):
        if args is None:
            args = {}

        event = self.attached_event
        assert isinstance(event, AVGECardHPChange)
        # rounded up halving: x - floor(x/2) == ceil(x/2)
        event.modify_magnitude(-math.floor(event.magnitude / 2))
        return Response(ResponseType.ACCEPT, Notify('Damper Pedal: Incoming damage halved.', all_players, default_timeout))


class DavidMan(AVGECharacterCard):
    _ACTIVE_CHOICE_KEY = "davidman_active_choice"
    _RANDOM_PICK_KEY = "davidman_active_pick"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.PIANO, 1, 2)
        self.atk_1_name = 'Damper Pedal'
        self.active_name = 'Reverse Heist'

    def can_play_active(self) -> bool:
        if self.env.player_turn != self.player:
            return False
        discard = self.player.cardholders[Pile.DISCARD]
        if len(discard) == 0:
            return False
        _, already_used_idx = self.env.check_history(
            self.env.round_id,
            PlayCharacterCard,
            {
                'card': self,
                'card_action': ActionTypes.ACTIVATE_ABILITY,
                'caller': self,
            },
        )
        return already_used_idx == -1

    def active(self) -> Response:
        discard = self.player.cardholders[Pile.DISCARD]
        deck = self.player.cardholders[Pile.DECK]
        if len(discard) == 0:
            return Response(ResponseType.CORE, Data())

        if self.env.cache.get(self, DavidMan._RANDOM_PICK_KEY, None) is None:
            topick = random.choice(list(discard))
            self.env.cache.set(self, DavidMan._RANDOM_PICK_KEY, topick)

        choice = self.env.cache.get(self, DavidMan._ACTIVE_CHOICE_KEY, None, True)
        if choice is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            self.player,
                            [DavidMan._ACTIVE_CHOICE_KEY],
                            lambda r: True,
                            ActionTypes.ACTIVATE_ABILITY,
                            self,
                            StrSelectionQuery(
                                'Reverse Heist: Put the chosen discard on top or bottom of your deck?',
                                ['top', 'bottom'],
                                ['top', 'bottom'],
                                False,
                                False,
                            )
                        )
                    ]),
            )

        chosen_card = self.env.cache.get(self, DavidMan._RANDOM_PICK_KEY, None, True)
        new_idx = 0 if choice == 'top' else None

        def generate_packet() -> PacketType:
            packet: PacketType = []
            if not isinstance(chosen_card, AVGECard) or chosen_card not in discard:
                return packet
            packet.append(
                EmptyEvent(
                    ActionTypes.ACTIVATE_ABILITY,
                    self,
                    ResponseType.CORE,
                    RevealCards(
                        'Reverse Heist: Randomly selected discard card',
                        [self.player.unique_id],
                        default_timeout,
                        [chosen_card],
                    ),
                )
            )
            packet.append(
                TransferCard(
                    chosen_card,
                    discard,
                    deck,
                    ActionTypes.ACTIVATE_ABILITY,
                    self,
                    None,
                    new_idx,
                )
            )
            return packet

        self.propose(AVGEPacket([generate_packet], AVGEEngineID(self, ActionTypes.ACTIVATE_ABILITY, DavidMan)))
        return self.generic_response(self, ActionTypes.ACTIVATE_ABILITY)

    def atk_1(self, card: AVGECharacterCard) -> Response:
        def gen() -> PacketType:
            packet: PacketType = []
            packet.append(
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    20,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PIANO,
                    ActionTypes.ATK_1,
                    None,
                    card,
                )
            )
            return packet

        card.propose(
            AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_1, DavidMan))
        )

        card.add_listener(DavidNextAttackHalvedModifier(card))
        return self.generic_response(card, ActionTypes.ATK_1)
