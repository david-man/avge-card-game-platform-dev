from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import AVGECardHPChange, InputEvent


class KanaImmenseAuraModifier(AVGEModifier):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(
            identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, KanaTakizawa),
            group=EngineGroup.EXTERNAL_MODIFIERS_3,
        )
        self.owner_card = owner_card

    def event_match(self, event):
        if not isinstance(event, AVGECardHPChange):
            return False
        if event.target_card != self.owner_card:
            return False
        if event.modifier_type != AVGEAttributeModifier.SUBSTRACTIVE:
            return False
        if event.change_type == CardType.ALL:
            return False
        return event.catalyst_action in [ActionTypes.ATK_1, ActionTypes.ATK_2]

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def modify(self, args=None):
        if args is None:
            args = {}
        event = self.attached_event
        assert isinstance(event, AVGECardHPChange)
        event.modify_magnitude(-10)
        return Response(ResponseType.ACCEPT, Notify('Immense Aura: -10 damage from attack.', all_players, default_timeout))


class KanaTakizawa(AVGECharacterCard):
    _D6_ROLL_KEY = 'kanatakizawa_d6_roll'
    _PREV_ROLL_KEY = 'kanatakizawa_prev_roll'
    _ROLL_COUNT_KEY = 'kanatakizawa_roll_count'

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.WOODWIND, 2, 3)
        self.has_passive = True
        self.atk_1_name = 'Flutter Tongue'

    def passive(self) -> Response:
        self.add_listener(KanaImmenseAuraModifier(self))
        return Response(ResponseType.CORE, Data())

    def _roll_interrupt(self, card: AVGECharacterCard) -> Response:
        return Response(
            ResponseType.INTERRUPT,
            Interrupt[AVGEEvent]([
                InputEvent(
                    card.player,
                    [KanaTakizawa._D6_ROLL_KEY],
                    lambda r: True,
                    ActionTypes.ATK_1,
                    card,
                    D6Data('Flutter Tongue: Roll a D6.'),
                )
            ]),
        )

    def atk_1(self, card: AVGECharacterCard) -> Response:
        missing = object()
        roll = card.env.cache.get(card, KanaTakizawa._D6_ROLL_KEY, missing, True)
        if roll is missing:
            return self._roll_interrupt(card)
        assert isinstance(roll, int)

        prev_roll = card.env.cache.get(card, KanaTakizawa._PREV_ROLL_KEY, None, True)
        roll_count = card.env.cache.get(card, KanaTakizawa._ROLL_COUNT_KEY, 0, True)
        assert isinstance(roll_count, int)
        roll_count += 1

        is_done = isinstance(prev_roll, int) and (prev_roll + roll == 7)
        if not is_done:
            card.env.cache.set(card, KanaTakizawa._PREV_ROLL_KEY, roll)
            card.env.cache.set(card, KanaTakizawa._ROLL_COUNT_KEY, roll_count)
            return self._roll_interrupt(card)

        def one_hit() -> PacketType:
            packet: PacketType = []
            active = card.player.opponent.get_active_card()
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        10,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.WOODWIND,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )
            return packet

        packet: PacketType = [one_hit for _ in range(roll_count)]
        card.propose(AVGEPacket(packet, AVGEEngineID(card, ActionTypes.ATK_1, KanaTakizawa)))
        return self.generic_response(card, ActionTypes.ATK_1)
