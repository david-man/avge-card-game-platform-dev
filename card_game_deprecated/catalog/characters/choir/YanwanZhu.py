from __future__ import annotations

from typing import cast

from card_game.avge_abstracts import *
from card_game.constants import *
from card_game.engine.engine_constants import EngineGroup


class _YanwanStartReactor(AVGEReactor):
    def __init__(self, owner_card: AVGECharacterCard):
        super().__init__(identifier=AVGEEngineID(owner_card, ActionTypes.PASSIVE, YanwanZhu), group=EngineGroup.EXTERNAL_REACTORS)
        self.owner_card = owner_card

    def event_match(self, event):
        from card_game.internal_events import PhasePickCard

        if not isinstance(event, PhasePickCard):
            return False
        if self.owner_card.cardholder is None or self.owner_card.cardholder.pile_type != Pile.ACTIVE:
            return False
        if self.owner_card.player is None or event.env.player_turn != self.owner_card.player:
            return False
        if len(self.owner_card.energy) != 2:
            return False
        damaged_teammates = [
            c for c in self.owner_card.player.get_cards_in_play()
            if isinstance(c, AVGECharacterCard) and c != self.owner_card and c.hp < c.max_hp
        ]
        if len(damaged_teammates) == 0:
            return False
        return True

    def event_effect(self) -> bool:
        return True

    def update_status(self):
        return

    def react(self, args=None):
        from card_game.internal_events import InputEvent, AVGECardHPChange

        owner = self.owner_card
        env = owner.env
        candidates = [
            c for c in owner.player.get_cards_in_play()
            if isinstance(c, AVGECharacterCard) and c != owner and c.hp < c.max_hp
        ]
        if len(candidates) == 0:
            return Response(ResponseType.ACCEPT, Data())

        missing = object()
        chosen = env.cache.get(owner, YanwanZhu._HEAL_TARGET_KEY, missing, True)
        if chosen is missing:
            return Response(
                ResponseType.INTERRUPT,
                Interrupt[InputEvent]([
                        InputEvent(
                            owner.player,
                            [YanwanZhu._HEAL_TARGET_KEY],
                            lambda r: True,
                            ActionTypes.PASSIVE,
                            owner,
                            CardSelectionQuery(
                                "Bass Boost: Choose a different character to heal 30 damage (or None).",
                                candidates,
                                candidates,
                                True,
                                False,
                            )
                        )
                    ]),
            )
        if chosen is None:
            return Response(ResponseType.ACCEPT, Data())

        if isinstance(chosen, AVGECharacterCard) and chosen in candidates:
            def generate() -> PacketType:
                return [
                    AVGECardHPChange(
                        chosen,
                        30,
                        AVGEAttributeModifier.ADDITIVE,
                        CardType.CHOIR,
                        ActionTypes.PASSIVE,
                        Notify("Bass Boost: Healed for 30", all_players, default_timeout),
                        owner,
                    )
                ]

            self.propose(
                AVGEPacket(
                    [generate],
                    AVGEEngineID(owner, ActionTypes.PASSIVE, YanwanZhu),
                ),
                1,
            )
        return Response(ResponseType.ACCEPT, Data())
    
    def __str__(self):
        return "Yanwan Zhu: Bass Boost"


class YanwanZhu(AVGECharacterCard):
    _HEAL_TARGET_KEY = "yanwan_heal_target"

    def __init__(self, unique_id):
        super().__init__(unique_id, 100, CardType.CHOIR, 1, 3)
        self.atk_1_name = 'Intense Voice'
        self.has_passive = True

    def passive(self) -> Response:
        self.add_listener(_YanwanStartReactor(self))
        return Response(ResponseType.CORE, Data())

    def atk_1(self, card: AVGECharacterCard, caller_action : ActionTypes) -> Response:
        from card_game.internal_events import AVGECardHPChange
        def gen_active() -> PacketType:
            return [
                    AVGECardHPChange(
                        card.player.opponent.get_active_card(),
                        60,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.CHOIR,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    )
                ]
        def gen_bench() -> PacketType:
            p : PacketType = [
                    AVGECardHPChange(
                        cast(AVGECharacterCard, c),
                        10,
                        AVGEAttributeModifier.SUBSTRACTIVE,
                        CardType.CHOIR,
                        ActionTypes.ATK_1,
                        None,
                        card,
                    ) for c in card.player.opponent.cardholders[Pile.BENCH]
                ]
            return p
        card.propose(
            AVGEPacket(
                [gen_active, gen_bench],
                AVGEEngineID(card, ActionTypes.ATK_1, YanwanZhu),
            )
        )

        return Response(ResponseType.CORE, Notify(f"{str(card)} used Intense Voice!", all_players, default_timeout))
