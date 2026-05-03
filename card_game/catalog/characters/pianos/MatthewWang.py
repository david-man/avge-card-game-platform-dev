from __future__ import annotations

from card_game.avge_abstracts import *

from card_game.constants import *
from card_game.engine.engine_constants import *
from card_game.internal_events import InputEvent, TransferCard, AVGECardHPChange


class _MatthewTurnBeginReactor(AVGEReactor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, MatthewWang), group=EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card

    def event_match(self, event):
        from card_game.internal_events import PhasePickCard

        if not isinstance(event, PhasePickCard):
            return False
        if self.owner_card.cardholder is None or self.owner_card.cardholder.pile_type != Pile.ACTIVE:
            return False
        return self.owner_card.player == self.owner_card.env.player_turn and self.owner_card == self.owner_card.player.get_active_card()

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def react(self, args=None):
        if args is None:
            args = {}

        owner = self.owner_card
        env = owner.env
        deck = owner.player.cardholders[Pile.DECK]
        if len(deck) == 0:
            return Response(ResponseType.ACCEPT, Data())

        res = env.cache.get(owner, MatthewWang._COIN_KEY, None)
        if res is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            owner.player,
                            [MatthewWang._COIN_KEY],
                            lambda r: True,
                            ActionTypes.PASSIVE,
                            owner,
                            CoinflipData('Pot of Greed: Flip a coin!')
                        )
                    ]),
            )

        if int(res) != 1:
            env.cache.delete(owner, MatthewWang._COIN_KEY)
            return Response(ResponseType.ACCEPT, Data())

        choice = env.cache.get(owner, MatthewWang._DRAW_CHOICE_KEY, None, True)
        if choice is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            owner.player,
                            [MatthewWang._DRAW_CHOICE_KEY],
                            lambda r: True,
                            ActionTypes.PASSIVE,
                            owner,
                            StrSelectionQuery(
                                'Pot of Greed: Draw one extra card (2 instead of 1)?',
                                ['Yes', 'No'],
                                ['Yes', 'No'],
                                False,
                                False,
                            )
                        )
                    ]),
            )
        env.cache.delete(owner, MatthewWang._COIN_KEY)
        if choice == 'Yes':
            def draw_top() -> PacketType:
                packet: PacketType = []
                if len(deck) == 0:
                    return packet
                packet.append(
                    TransferCard(
                        deck.peek(),
                        deck,
                        owner.player.cardholders[Pile.HAND],
                        ActionTypes.PASSIVE,
                        owner,
                        Notify("Pot of Greed: Drawing an extra card", all_players, default_timeout),
                    )
                )
                return packet

            owner.propose(
                AVGEPacket([
                    draw_top
                ], AVGEEngineID(owner, ActionTypes.PASSIVE, MatthewWang)), 1
            )

        return Response(ResponseType.ACCEPT, Data())
    
    def __str__(self):
        return "Matthew Wang: Pot of Greed"


class MatthewWang(AVGECharacterCard):
    _COIN_KEY = "matthew_coin"
    _DRAW_CHOICE_KEY = "matthew_draw_choice"

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.PIANO, 2, 2)
        self.atk_1_name = 'Arpeggios'
        self.has_passive = True

    def passive(self) -> Response:
        self.add_listener(_MatthewTurnBeginReactor(self))
        return Response(ResponseType.CORE, Data())

    def atk_1(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        def generate_packet() -> PacketType:
            active = card.player.opponent.get_active_card()
            packet: PacketType = []
            if isinstance(active, AVGECharacterCard):
                packet.append(
                    AVGECardHPChange(
                        active,
                        40,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.PIANO,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )
            return packet

        card.propose(
            AVGEPacket([
                generate_packet
            ], AVGEEngineID(card, ActionTypes.ATK_1, MatthewWang))
        )

        return self.generic_response(card, ActionTypes.ATK_1)
