from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import AVGECardHPChange, InputEvent


class JaydenBrownFourLeafCloverReactor(AVGEReactor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(
            identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, JaydenBrown),
            group=EngineGroup.EXTERNAL_REACTORS,
        )
        self.owner_card = owner_card

    def event_match(self, event):
        if not isinstance(event, InputEvent):
            return False
        if not isinstance(event.query_data, CoinflipData):
            return False
        if self.owner_card.cardholder is None or self.owner_card.cardholder.pile_type != Pile.ACTIVE:
            return False
        if(event.player_for != self.owner_card.player):
            return False
        if self._has_prior_coinflip_this_turn(event.player_for):
            return False
        return True

    def _has_prior_coinflip_this_turn(self, player_for: AVGEPlayer) -> bool:
        env = self.owner_card.env
        idx = 0
        kwargs = {'player_for': player_for}
        while True:
            prior_event, idx = env.check_history(env.round_id, InputEvent, kwargs, idx)
            if prior_event is None:
                return False
            if isinstance(prior_event, InputEvent) and isinstance(prior_event.query_data, CoinflipData):
                return True
            idx += 1

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def make_announcement(self) -> bool:
        return True

    def package(self):
        return 'JaydenBrown Four-leaf Clover Reactor'

    def react(self, args=None):
        if args is None:
            args = {}
        event = self.attached_event
        assert isinstance(event, InputEvent)

        env = self.owner_card.env
        choice = env.cache.get(self.owner_card, JaydenBrown._CHOICE, None, True)
        if choice is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                    InputEvent(
                        self.owner_card.player,
                        [JaydenBrown._CHOICE],
                        lambda r: True,
                        ActionTypes.PASSIVE,
                        self.owner_card,
                        StrSelectionQuery(
                            'Four-leaf Clover: Treat this first coin flip as heads?',
                            ['Yes', 'No'],
                            ['Yes', 'No'],
                            False,
                            False,
                        ),
                    )
                ]),
            )

        if choice == 'Yes' and len(event.input_keys) > 0:
            env.cache.set(self.owner_card, event.input_keys[0], 1)
            return Response(ResponseType.CORE, Notify('Four-leaf Clover! Turned the first coin flip to heads', all_players, default_timeout))
        return Response(ResponseType.CORE, Data())

class JaydenBrown(AVGECharacterCard):
    _D6_ROLL_KEY = 'jayden_d6_roll'
    _CHOICE = 'jayden_coin_choice'

    def __init__(self, unique_id):
        super().__init__(unique_id, 90, CardType.WOODWIND, 1, 3)
        self.has_passive = True
        self.atk_1_name = 'Hyper-Ventilation!'

    def passive(self) -> Response:
        self.add_listener(JaydenBrownFourLeafCloverReactor(self))
        return Response(ResponseType.CORE, Data())

    def atk_1(self, card: AVGECharacterCard) -> Response:
        missing = object()
        roll = card.env.cache.get(card, JaydenBrown._D6_ROLL_KEY, missing, True)
        if roll is missing:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            card.player,
                            [JaydenBrown._D6_ROLL_KEY],
                            lambda r: True,
                            ActionTypes.ATK_1,
                            card,
                            D6Data('Hyper-Ventilation!: Roll a D6.')
                        )
                    ]),
            )

        if not isinstance(roll, int):
            return Response(ResponseType.CORE, Data())

        damage = 30 + 10 * int(roll)

        def generate_packet() -> PacketType:
            active = card.player.opponent.get_active_card()
            packet: PacketType = []
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        damage,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.WOODWIND,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, JaydenBrown)))
        return self.generic_response(card, ActionTypes.ATK_1)
