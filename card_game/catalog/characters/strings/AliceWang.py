from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import AVGECardHPChange, InputEvent, TransferCard, EmptyEvent


class _AliceHandEqualizerReactor(AVGEReactor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(
            identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, AliceWang),
            group=EngineGroup.EXTERNAL_REACTORS,
        )
        self.owner_card = owner_card

    def event_match(self, event):
        from card_game.internal_events import TurnEnd

        if not isinstance(event, TurnEnd):
            return False
        if self.owner_card.cardholder is None or self.owner_card.cardholder.pile_type not in [Pile.ACTIVE, Pile.BENCH]:
            return False
        if self.owner_card.player is None or self.owner_card.player.opponent is None:
            return False
        if event.env.player_turn != self.owner_card.player.opponent:
            return False

        owner_hand = self.owner_card.player.cardholders[Pile.HAND]
        opponent_hand = self.owner_card.player.opponent.cardholders[Pile.HAND]
        return len(opponent_hand) > len(owner_hand)

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def react(self, args=None):
        if args is None:
            args = {}

        owner = self.owner_card
        owner_hand = owner.player.cardholders[Pile.HAND]
        opponent = owner.player.opponent
        opponent_hand = opponent.cardholders[Pile.HAND]
        opponent_discard = opponent.cardholders[Pile.DISCARD]

        extra_cards = len(opponent_hand) - len(owner_hand)

        keys = [AliceWang._CARDS_TO_DISCARD_BASE_KEY + str(i) for i in range(extra_cards)]
        discarded_cards = [owner.env.cache.get(owner, key, None, True) for key in keys]
        if len(discarded_cards) == 0 or discarded_cards[0] is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[AVGEEvent]([
                        InputEvent(
                            opponent,
                            keys,
                            lambda r: True,
                            ActionTypes.PASSIVE,
                            owner,
                            CardSelectionQuery(
                                'Euclidean Algorithm: Choose cards to discard until hand sizes match.',
                                list(opponent_hand),
                                list(opponent_hand),
                                False,
                                False,
                            )
                        )
                    ]),
            )

        def apply_discards() -> PacketType:
            packet: PacketType = []
            for selected in discarded_cards:
                if isinstance(selected, AVGECard) and selected in opponent_hand:
                    packet.append(
                        TransferCard(
                            selected,
                            opponent_hand,
                            opponent_discard,
                            ActionTypes.PASSIVE,
                            owner,
                            None,
                        )
                    )
            return packet

        owner.propose(
            AVGEPacket([apply_discards], AVGEEngineID(owner, ActionTypes.PASSIVE, AliceWang)),
            1,
        )
        return Response(ResponseType.ACCEPT, Notify('Euclidean Algorithm: Opponent discards until hand sizes match.', all_players, default_timeout))

class AliceWang(AVGECharacterCard):
    _CARDS_TO_DISCARD_BASE_KEY = "alice_cards_to_discard_"

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.STRING, 2, 2)
        self.atk_1_name = 'Vibrato'
        self.has_passive = True

    def passive(self) -> Response:
        self.add_listener(_AliceHandEqualizerReactor(self))
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
                        CardType.STRING,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                )
            return packet

        card.propose(AVGEPacket([generate_packet], AVGEEngineID(card, ActionTypes.ATK_1, AliceWang)))
        return self.generic_response(card, ActionTypes.ATK_1)
