from __future__ import annotations

import random
import math

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


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
        if(not isinstance(event.caller_card, AVGECharacterCard)):
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


class DavidMan(AVGECharacterCard):
    _ACTIVE_USED_KEY = "davidman_active_used"
    _ACTIVE_CHOICE_KEY = "davidman_active_choice"
    _RANDOM_PICK_KEY = "davidman_active_pick"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.PIANO, 1, 2)
        self.has_atk_1 = True
        self.has_atk_2 = False
        self.has_passive = False
        self.has_active = True

    @staticmethod
    def can_play_active(card: AVGECharacterCard) -> bool:
        discard = card.player.cardholders[Pile.DISCARD]
        if len(discard) == 0:
            return False
        used = card.env.cache.get(card, DavidMan._ACTIVE_USED_KEY, None)
        return used != card.env.round_id

    @staticmethod
    def active(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import InputEvent, TransferCard, EmptyEvent

        discard = card.player.cardholders[Pile.DISCARD]
        deck = card.player.cardholders[Pile.DECK]
        if(len(discard) == 0):
            return card.generate_response(data={MESSAGE_KEY: "No cards in discard to use!"})
        card.env.cache.set(card, DavidMan._ACTIVE_USED_KEY, card.env.round_id)

        if card.env.cache.get(card, DavidMan._RANDOM_PICK_KEY, None) is None:
            topick = random.choice(list(discard))
            card.env.cache.set(card, DavidMan._RANDOM_PICK_KEY, topick)

        choice = card.env.cache.get(card, DavidMan._ACTIVE_CHOICE_KEY, None, True)
        if choice is None:
            return card.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            card.player,
                            [DavidMan._ACTIVE_CHOICE_KEY],
                            InputType.BINARY,
                            lambda r : True,
                            ActionTypes.ACTIVATE_ABILITY,
                            card,
                            {LABEL_FLAG: "david_man_top_bottom",
                             "card": card.env.cache.get(card, DavidMan._RANDOM_PICK_KEY, None)},
                        )
                    ]
                },
            )

        chosen_card = card.env.cache.get(card, DavidMan._RANDOM_PICK_KEY, None, True)
        new_idx = 0 if choice == "top" else None

        def generate_packet() -> PacketType:
            if chosen_card is None or chosen_card not in discard:
                return [EmptyEvent(ActionTypes.ACTIVATE_ABILITY, card,response_data={MESSAGE_KEY:"DavidMan active had no valid discard target at resolve."})]
            return [
                TransferCard(chosen_card, discard, deck, ActionTypes.ACTIVATE_ABILITY, card, new_idx)]
        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ACTIVATE_ABILITY, DavidMan)))
        return card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange
        def gen() -> PacketType:
            return [
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    20,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PIANO,
                    ActionTypes.ATK_1,
                    card,
                )
            ]
        card.propose(
            AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_1, DavidMan))
        )

        card.add_listener(DavidNextAttackHalvedModifier(card))
        return card.generate_response()
