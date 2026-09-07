from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....core.AVGEIOManager import CardSelectionQuery

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....constants import User


class HanleiGao(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.PERCUSSION

    def base_retreat_cost(self) -> int:
        return 2

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._StickTrick(), ActionTypes.ATK_2: self._TrickyRhythms()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _StickTrick(Attack):
        '''Byte-identical to LoangChiang's atk_1, implemented independently per policy.'''

        def __init__(self):
            super().__init__(
                name="Stick Trick",
                description="Deal 20 damage to the opposing active. You may swap with a benched character for free.",
                atk_type=ActionTypes.ATK_1,
                cost=2,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            player = env.players[card.owner]
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), HanleiGao)

            events: list[Event | Generator] = [AVGECardHPChangeEvent(
                _id, target, 20, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PERCUSSION, env,
            )]

            bench = player.card_piles[DeckType.BENCH]
            active_holder = player.card_piles[DeckType.ACTIVE_CARD]
            bench_candidates = [c for c in bench.cards_holding if isinstance(c, AVGECharacterCard)]
            if bench_candidates:
                picked = await env.report(CardSelectionQuery(
                    card.owner,
                    "Stick Trick: You may swap with a benched character for free.",
                    1,
                    cast(list[AVGECard], bench_candidates),
                    list(bench.cards_holding),
                    True,
                    False,
                ), _id)
                if picked:
                    pick = picked[0]
                    assert isinstance(pick, AVGECharacterCard)
                    events.append(TransferCard(_id, pick, bench, active_holder, env))
                    events.append(TransferCard(_id, card, active_holder, bench, env))

            env.push_packet(Packet(_id, events))

    class _TrickyRhythms(Attack):
        def __init__(self):
            super().__init__(
                name="Tricky Rhythms",
                description="Deal 50 damage to each opposing character carrying a tool, and strip all their tools to the opponent's hand.",
                atk_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            opponent_hand = opponent.card_piles[DeckType.HAND]
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), HanleiGao)

            opposing_chars: list[AVGECharacterCard] = [
                c for c in opponent.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
            ] + [
                c for c in opponent.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
            ]

            events: list[Event | Generator] = []
            for c in opposing_chars:
                if len(c.tools_attached.cards_holding) > 0:
                    events.append(AVGECardHPChangeEvent(
                        _id, c, 50, AVGEAttributeModifier.SUBSTRACTIVE, CardType.PERCUSSION, env,
                    ))
                for tool in list(c.tools_attached.cards_holding):
                    events.append(TransferCard(_id, tool, c.tools_attached, opponent_hand, env))

            env.push_packet(Packet(_id, events))
