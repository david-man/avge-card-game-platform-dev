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
        if not isinstance(event, AtkPhase):
            return False
        if self.owner_card.cardholder is None or self.owner_card.cardholder.pile_type != Pile.BENCH:
            return False
        active = event.env.player_turn.get_active_card()
        if not isinstance(active, AVGECharacterCard):
            return False
        return len(active.energy) >= 2

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        if self.owner_card.env is None:
            self.invalidate()

    def assess(self, args=None):
        if args is None:
            args = {}
        from card_game.internal_events import PlayCharacterCard

        current_player = self.owner_card.env.player_turn
        active = current_player.get_active_card()
        if not isinstance(active, AVGECharacterCard):
            return Response(ResponseType.ACCEPT, Data())

        chosen = self.owner_card.env.cache.get(self.owner_card, RossWilliams._PASSIVE_KEY, None, True)
        if chosen is None:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[InputEvent]([
                        InputEvent(
                            current_player,
                            [RossWilliams._PASSIVE_KEY],
                            lambda r: True,
                            ActionTypes.PASSIVE,
                            self.owner_card,
                            StrSelectionQuery(
                                "I Am Become Ross: Use Ross's attack?",
                                ["Yes", "No"],
                                ["Yes", "No"],
                                False,
                                False,
                            )
                        )
                    ]),
            )

        if not chosen == 'Yes':
            return Response(ResponseType.ACCEPT, Data())

        packet = [
            PlayCharacterCard(self.owner_card, ActionTypes.ATK_1, ActionTypes.PASSIVE, active),
            AVGEPlayerAttributeChange(current_player, AVGEPlayerAttribute.ATTACKS_LEFT, 1, AVGEAttributeModifier.SUBSTRACTIVE, ActionTypes.ENV, self.owner_card.env, None),
        ]
        self.owner_card.propose(
            AVGEPacket(packet, AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, RossWilliams))
        )
        return Response(ResponseType.FAST_FORWARD, Notify(str(active) + " used Ross's attack!", all_players, default_timeout))


class RossWilliams(AVGECharacterCard):
    _PASSIVE_KEY = "ross_ross_passive_key"
    _ATTACK_KEY = "ross_attk_key"
    _ATTACK_HAND_KEY = "ross_attk_hand_key"

    def __init__(self, unique_id):
        super().__init__(unique_id, 110, CardType.CHOIR, 2, 2)
        self.atk_1_name = 'Ross Attack!'
        self.has_passive = True

    def passive(self: AVGECharacterCard) -> Response:
        self.add_listener(_RossPassiveAssessor(self))
        return Response(ResponseType.CORE, Data())

    def atk_1(self, card: AVGECharacterCard) -> Response:
        from card_game.internal_events import AVGECardHPChange

        player = card.player
        opponent = player.opponent

        player_has = any(isinstance(c, RossWilliams) for c in player.cardholders[Pile.BENCH])
        opp_has = any(isinstance(c, RossWilliams) for c in opponent.cardholders[Pile.BENCH])

        if player_has and opp_has:
            return Response(ResponseType.CORE, Notify(f"{str(card)} used Ross Attack, but it did nothing...", all_players, default_timeout))

        if player_has:
            discard = player.cardholders[Pile.DISCARD]
            hand = player.cardholders[Pile.HAND]

            if len(discard) == 0:
                return Response(ResponseType.CORE, Notify(f"{str(card)} used Ross Attack, but there were no cards in discard.", all_players, default_timeout))

            choice = player.env.cache.get(card, RossWilliams._ATTACK_HAND_KEY, None, True)
            if choice is None:
                discard_cards = list(discard)
                return Response(
                    ResponseType.INTERRUPT,
                    Interrupt[InputEvent]([
                            InputEvent(
                                player,
                                [RossWilliams._ATTACK_HAND_KEY],
                                lambda r: True,
                                ActionTypes.ATK_1,
                                card,
                                CardSelectionQuery(
                                    "Ross Attack!: Choose a card from discard to put in your hand",
                                    discard_cards,
                                    discard_cards,
                                    False,
                                    False,
                                )
                            )
                        ]),
                )

            card.propose(
                AVGEPacket(
                    [
                        TransferCard(choice, discard, hand, ActionTypes.ATK_1, card, None)
                    ],
                    AVGEEngineID(card, ActionTypes.ATK_1, RossWilliams),
                )
            )
            return Response(ResponseType.CORE, Notify(f"{str(card)} used Ross Attack!", all_players, default_timeout))

        if opp_has:
            targets = opponent.get_cards_in_play()
            target = player.env.cache.get(card, RossWilliams._ATTACK_KEY, None, True)
            if target is None:
                return Response(
                    ResponseType.INTERRUPT,
                    Interrupt[InputEvent]([
                            InputEvent(
                                card.player,
                                [RossWilliams._ATTACK_KEY],
                                lambda r: True,
                                ActionTypes.ATK_1,
                                card,
                                CardSelectionQuery("Ross Attack!: Choose a card to attack", targets, targets, False, False)
                            )
                        ]),
                )
            card.propose(
                AVGEPacket(
                    [
                        AVGECardHPChange(
                            target,
                            20,
                            AVGEAttributeModifier.SUBSTRACTIVE,
                            CardType.CHOIR,
                            ActionTypes.ATK_1,
                            None,
                            card,
                        )
                    ],
                    AVGEEngineID(card, ActionTypes.ATK_1, RossWilliams),
                )
            )
            return Response(ResponseType.CORE, Notify(f"{str(card)} used Ross Attack!", all_players, default_timeout))

        return Response(ResponseType.CORE, Notify(f"{str(card)} used Ross Attack, but it did nothing...", all_players, default_timeout))
