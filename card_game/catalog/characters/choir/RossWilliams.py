from __future__ import annotations

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup
from card_game.internal_events import InputEvent, AtkPhase, AVGEPlayerAttributeChange, TransferCard


class _RossPassiveAssessor(AVGEAssessor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, RossWilliams), group=EngineGroup.EXTERNAL_MODIFIERS_2)
        self.owner_card = owner_card

    def event_match(self, event):
        return isinstance(event, AtkPhase) and \
            event.player == self.owner_card.player and \
            self.owner_card.cardholder.pile_type == Pile.BENCH and \
            len(self.owner_card.player.get_active_card().energy) >= 2

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        if self.owner_card.env is None:
            self.invalidate()

    def make_announcement(self) -> bool:
        return True

    def package(self):
        return "RossWilliams Passive Assessor"

    def assess(self, args=None):
        if args is None:
            args = {}
        from card_game.internal_events import PlayCharacterCard, TurnEnd

        active: AVGECharacterCard = self.owner_card.player.get_active_card()
        chosen = self.owner_card.env.cache.get(self.owner_card, RossWilliams._PASSIVE_KEY, None, True)
        if chosen is None:
            return self.generate_response(
                ResponseType.INTERRUPT,
                {
                    INTERRUPT_KEY: [
                        InputEvent(
                            self.owner_card.player,
                            [RossWilliams._PASSIVE_KEY],
                            InputType.BINARY,
                            lambda r: True,
                            ActionTypes.PASSIVE,
                            self.owner_card,
                            {"query_label": "ross_use_atk1"},
                        )
                    ]
                },
            )

        if not chosen:
            return self.generate_response()

        packet = [
            PlayCharacterCard(self.owner_card, ActionTypes.ATK_1, ActionTypes.PASSIVE, active),
            AVGEPlayerAttributeChange(self.owner_card.player, AVGEPlayerAttribute.ATTACKS_LEFT, 1, AVGEAttributeModifier.SUBSTRACTIVE, ActionTypes.ENV, None),
            TurnEnd(self.owner_card.env, ActionTypes.ENV, None),
        ]
        self.owner_card.propose(
            AVGEPacket(packet, AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, RossWilliams))
        )
        return self.generate_response(ResponseType.FAST_FORWARD)


class RossWilliams(AVGECharacterCard):
    _PASSIVE_KEY = "ross_ross_passive_key"
    _ATTACK_KEY = "ross_attk_key"

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.CHOIR, 1, 2)
        self.has_atk_1 = True
        self.atk_1_cost = 2
        self.has_atk_2 = False
        self.has_passive = True
        self.has_active = False

    @staticmethod
    def passive(card: AVGECharacterCard) -> Response:
        card.add_listener(_RossPassiveAssessor(card))
        return card.generate_response()

    @staticmethod
    def atk_1(card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        player = card.player
        opponent = player.opponent

        player_has = any(isinstance(c, RossWilliams) for c in player.cardholders[Pile.BENCH])
        opp_has = any(isinstance(c, RossWilliams) for c in opponent.cardholders[Pile.BENCH])

        if player_has and opp_has:
            return card.generate_response()

        if player_has and not opp_has:
            deck = player.cardholders[Pile.DECK]
            hand = player.cardholders[Pile.HAND]
            def generate_packet() -> PacketType:
                def gen() -> PacketType:
                    return [TransferCard(deck.peek(), deck, hand, ActionTypes.ATK_1, card)]
                return [gen for _ in range(min(2, len(deck)))]

            card.propose(
                AVGEPacket(
                    [generate_packet],
                    AVGEEngineID(card, ActionTypes.ATK_1, RossWilliams),
                )
            )
            return card.generate_response()

        if opp_has and not player_has:
            targets = opponent.get_cards_in_play()
            target = player.env.cache.get(card, RossWilliams._ATTACK_KEY, None, True)
            if target is None:
                return card.generate_response(
                    ResponseType.INTERRUPT,
                    {
                        INTERRUPT_KEY: [
                            InputEvent(
                                card.player,
                                [RossWilliams._ATTACK_KEY],
                                InputType.SELECTION,
                                lambda r: True,
                                ActionTypes.ATK_1,
                                card,
                                {
                                    "query_label": "ross_atk1_target",
                                    "targets": targets,
                                    "display": targets
                                },
                            )
                        ]
                    },
                )
            card.propose(
                AVGEPacket(
                    [
                        AVGECardHPChange(
                            target,
                            50,
                            AVGEAttributeModifier.SUBSTRACTIVE,
                            CardType.CHOIR,
                            ActionTypes.ATK_1,
                            card,
                        )
                    ],
                    AVGEEngineID(card, ActionTypes.ATK_1, RossWilliams),
                )
            )

        return card.generate_response()
