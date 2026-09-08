from __future__ import annotations

import random
from typing import TYPE_CHECKING, cast

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard, ReorderDeck, PlayCharacterCard
from ....core.AVGEIOManager import CardSelectionQuery, BroadcastIO

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID
    from ....constants import User


class RachaelYuan(AVGECharacterCard):
    '''Byte-identical Circular Breathing streak formula to DesmondRoper/EvelynWu's
    atk_1, implemented independently.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.WOODWIND

    def base_retreat_cost(self) -> int:
        return 2

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._CircularBreathing(), ActionTypes.ATK_2: self._E2Reaction()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _CircularBreathing(Attack):
        def __init__(self):
            super().__init__(
                name="Circular Breathing",
                description="Deal 10 damage, plus 10 more per consecutive prior turn this attack was used (uncapped).",
                atk_type=ActionTypes.ATK_1,
                cost=1,
            )

        def _streak(self, card: AVGECharacterCard) -> int:
            env = card.env
            streak = 0
            chapter_increment = 2
            while streak < 4:
                event, _ = env.search_history(
                    PlayCharacterCard,
                    {"target_card": card, "action": ActionTypes.ATK_1},
                    increment=chapter_increment,
                    attribute_search=True,
                )
                if event is None:
                    break
                streak += 1
                chapter_increment += 2
            return streak

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), RachaelYuan)

            streak = self._streak(card)
            damage = 10 + (10 * streak)

            env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id, target, damage, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env,
            )]))

    class _E2Reaction(Attack):
        def __init__(self):
            super().__init__(
                name="E2 Reaction",
                description="If the opponent has at least 2 benched characters, you may shuffle one into their deck.",
                atk_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            opponent_bench = opponent.card_piles[DeckType.BENCH]
            opponent_deck = opponent.card_piles[DeckType.DECK]
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), RachaelYuan)

            bench_candidates = [c for c in opponent_bench.cards_holding if isinstance(c, AVGECharacterCard)]
            if len(bench_candidates) < 2:
                await env.broadcast(BroadcastIO(
                    f"{card} used E2 Reaction, but it didn't do anything...", default_timeout,
                ))
                return

            picked = await env.report(CardSelectionQuery(
                card.owner,
                "E2 Reaction: You may shuffle one opposing benched character into their deck.",
                1,
                cast(list[AVGECard], bench_candidates),
                cast(list[AVGECard], bench_candidates),
                True,
                False,
            ), _id)
            if not picked:
                return
            chosen = picked[0]

            events: list[Event | Generator] = [TransferCard(_id, chosen, opponent_bench, opponent_deck, env)]

            def _make_shuffle(deck: AVGEDeck = opponent_deck):
                def gen() -> list[AVGECard]:
                    return random.sample(deck.cards_holding, len(deck.cards_holding))
                return gen
            events.append(ReorderDeck(_id, opponent_deck, _make_shuffle(), env))

            env.push_packet(Packet(_id, events))
