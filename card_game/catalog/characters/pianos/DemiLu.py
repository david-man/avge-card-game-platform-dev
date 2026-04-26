from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import AVGECardHPChange
from card_game.catalog.stadiums.SteinertBasement import SteinertBasement, SteinertBasementAttackExtraCostAssessor
from card_game.catalog.stadiums.SteinertPracticeRoom import SteinertPracticeRoom, SteinertPracticeRoomAttackExtraCostAssessor


def _is_steinert_active(owner_card: AVGECharacterCard) -> bool:
    if owner_card.env is None or len(owner_card.env.stadium_cardholder) == 0:
        return False
    stadium = owner_card.env.stadium_cardholder.peek()
    return isinstance(stadium, (SteinertBasement, SteinertPracticeRoom))


class DemiLuDamageBlockModifier(AVGEAssessor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, DemiLu), group=EngineGroup.EXTERNAL_PRECHECK_1)
        self.owner_card = owner_card

    def event_match(self, event):
        from card_game.internal_events import AVGECardHPChange

        if not isinstance(event, AVGECardHPChange):
            return False
        if event.target_card != self.owner_card:
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if self.owner_card.cardholder.pile_type != Pile.BENCH:
            return False
        if event.catalyst_action not in [ActionTypes.ATK_1, ActionTypes.ATK_2]:
            return False
        if not isinstance(event.caller, AVGECharacterCard):
            return False
        if event.caller.player != self.owner_card.player.opponent:
            return False
        return _is_steinert_active(self.owner_card)

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return
    
    def assess(self, args=None):
        if args is None:
            args = {}
        return Response(ResponseType.FAST_FORWARD, Notify('Steinert Warrior: Demi Lu is immune to this attack.', all_players, default_timeout))


class DemiLuConstraint(AVGEConstraint):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, DemiLu))
        self.owner_card = owner_card

    def match(self, obj):
        from card_game.internal_events import PlayCharacterCard

        if self.owner_card.cardholder is None or self.owner_card.cardholder.pile_type != Pile.BENCH:
            return False
        if not _is_steinert_active(self.owner_card):
            return False
        if not isinstance(obj, (SteinertPracticeRoomAttackExtraCostAssessor, SteinertBasementAttackExtraCostAssessor)):
            return False
        event = obj.attached_event
        assert isinstance(event, PlayCharacterCard)
        return event.card == self.owner_card

    def response_data_on_attach(self, attached_to) -> Data:
        return Notify('Steinert Warrior: Demi Lu is not affected by 15 Minute Walk.', all_players, default_timeout)

    def update_status(self):
        return

    def package(self):
        return 'DemiLu Steinert Warrior Constraint'


class DemiLu(AVGECharacterCard):
    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.PIANO, 1, 3)
        self.atk_1_name = 'Four Hands'
        self.has_passive = True

    def passive(self) -> Response:
        self.add_listener(DemiLuDamageBlockModifier(self))
        self.add_constrainer(DemiLuConstraint(self))
        return Response(ResponseType.CORE, Data())

    def atk_1(self, card: AVGECharacterCard) -> Response:
        def gen() -> PacketType:
            bench_cards = [c for c in card.player.cardholders[Pile.BENCH] if c != card]
            found_piano = any(c.card_type == CardType.PIANO for c in bench_cards if isinstance(c, AVGECharacterCard))
            dmg = 80 if found_piano else 50

            packet: PacketType = []
            packet.append(
                AVGECardHPChange(
                    card.player.opponent.get_active_card(),
                    dmg,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.PIANO,
                    ActionTypes.ATK_1,
                    None,
                    card,
                )
            )
            return packet

        card.propose(
            AVGEPacket([gen], AVGEEngineID(card, ActionTypes.ATK_1, DemiLu))
        )

        return self.generic_response(card, ActionTypes.ATK_1)
