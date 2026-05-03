from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class _MeyaGuitarBoost(AVGEModifier):
    def __init__(self, owner_card: AVGECharacterCard, round_active: int):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.NONCHAR, MeyaGao), group=EngineGroup.EXTERNAL_MODIFIERS_2)
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
    
    def __str__(self):
        return "Meya Gao: Distortion Buff"


class _MeyaAttackBlockAssessor(AVGEAssessor):
    def __init__(self, owner_card: AVGECharacterCard, round_active: int):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, MeyaGao), group=EngineGroup.EXTERNAL_PRECHECK_1)
        self.card_blocked = owner_card
        self.round_active = round_active

    def event_match(self, event):
        from card_game.internal_events import PlayCharacterCard

        if not isinstance(event, PlayCharacterCard):
            return False
        if event.card_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]:
            return False
        if not isinstance(event.card, AVGECharacterCard):
            return False
        if event.caller != self.card_blocked:
            return False
        if self.card_blocked.env.round_id != self.round_active:
            return False
        return True

    def update_status(self):
        if self.card_blocked.env.round_id > self.round_active:
            self.invalidate()

    def assess(self) -> Response:
        assert isinstance(self.attached_event, PlayCharacterCard) and isinstance(self.attached_event.card, AVGECharacterCard)
        return Response(ResponseType.SKIP, Notify("Cannot attack this round due to Meya Gao's I See Your Soul!", [self.attached_event.card.player.unique_id], default_timeout))


class _MeyaDamageReactor(AVGEReactor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, MeyaGao), group=EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card

    def event_match(self, event):
        from card_game.internal_events import AVGECardHPChange

        if self.owner_card.cardholder is None or self.owner_card.cardholder.pile_type != Pile.ACTIVE:
            return False
        if not isinstance(event, AVGECardHPChange):
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        return event.target_card == self.owner_card and isinstance(event.caller, AVGECharacterCard)

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def react(self) -> Response:
        from card_game.internal_events import AVGECardHPChange

        event = self.attached_event
        assert isinstance(event, AVGECardHPChange)
        assert isinstance(event.caller, AVGECharacterCard)
        attacker: AVGECharacterCard = event.caller

        self.owner_card.add_listener(_MeyaAttackBlockAssessor(self.owner_card, self.owner_card.player.get_next_turn()))
        attacker.add_listener(_MeyaAttackBlockAssessor(attacker, attacker.player.get_next_turn()))

        return Response(ResponseType.ACCEPT, Data())
    
    def __str__(self):
        return "Meya Gao: Was hit"


class MeyaGao(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 120, CardType.GUITAR, 2, 3, 0)
        self.atk_1_name = 'Distortion'
        self.has_passive = True

    def passive(self) -> Response:
        self.add_listener(_MeyaDamageReactor(self))
        return Response(ResponseType.CORE, Data())

    def atk_1(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        from card_game.internal_events import AVGECardHPChange

        def gen() -> PacketType:
            packet: PacketType = []
            packet.append(
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    40,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.GUITAR,
                    ActionTypes.ATK_1,
                    None,
                    card,
                )
            )
            return packet

        card.propose(
            AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_1, MeyaGao))
        )
        card.add_listener(_MeyaGuitarBoost(card, card.player.get_next_turn()))

        return self.generic_response(card, ActionTypes.ATK_1)
