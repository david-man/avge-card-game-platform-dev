from __future__ import annotations

import random
from typing import TYPE_CHECKING

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, AVGEAttributeModifier, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard, ReorderDeck
from ....core.AVGEIOManager import CardSelectionQuery, RevealCards, D6Input, Notification

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID
    from ....constants import User


class KathySun(AVGECharacterCard):
    '''Flutter Tongue (atk_2) is byte-identical to KanaTakizawa's atk_1, implemented
    independently as a plain async loop.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.WOODWIND

    def base_retreat_cost(self) -> int:
        return 1

    def base_attacks(self) -> dict[ActionTypes, Attack]:
        return {ActionTypes.ATK_1: self._AnalysisParalysis(), ActionTypes.ATK_2: self._FlutterTongue()}

    def base_abilities(self) -> dict[ActionTypes, Ability]:
        return {}

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _AnalysisParalysis(Attack):
        def __init__(self):
            super().__init__(
                name="Analysis Paralysis",
                description="Reveal the opponent's hand. They choose up to 2 cards to shuffle into their own deck.",
                atk_type=ActionTypes.ATK_1,
                cost=1,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            opponent_hand = opponent.card_piles[DeckType.HAND]
            opponent_deck = opponent.card_piles[DeckType.DECK]
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), KathySun)

            choose_count = min(2, len(opponent_hand))
            if choose_count == 0:
                await env.report(Notification(
                    card.owner,
                    f"{card} tried to use Analysis Paralysis, but it did nothing...", default_timeout,
                ), _id)
                return

            await env.report(RevealCards(card.owner, list(opponent_hand.cards_holding)), _id)
            picked = await env.report(CardSelectionQuery(
                opponent.id,
                "Analysis Paralysis: Choose cards to shuffle into your deck.",
                choose_count,
                opponent_hand.cards_holding,
                opponent_hand.cards_holding,
                False,
                False,
            ), _id)

            if not picked:
                return

            events: list[Event | Generator] = [
                TransferCard(_id, chosen, opponent_hand, opponent_deck, env) for chosen in picked
            ]

            def _make_shuffle(deck: AVGEDeck = opponent_deck):
                def gen() -> list[AVGECard]:
                    return random.sample(deck.cards_holding, len(deck.cards_holding))
                return gen
            events.append(ReorderDeck(_id, opponent_deck, _make_shuffle(), env))

            env.push_packet(Packet(_id, events))

    class _FlutterTongue(Attack):
        def __init__(self):
            super().__init__(
                name="Flutter Tongue",
                description="Roll a D6 repeatedly until two consecutive rolls sum to 7. Deal 10 damage to the opposing active per roll taken.",
                atk_type=ActionTypes.ATK_2,
                cost=3,
            )

        async def __call__(self, card: AVGECharacterCard, caller_action: ActionTypes) -> None:
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.resolve_caller(caller_action), KathySun)

            prev_roll: int | None = None
            roll_count = 0
            while True:
                roll = await env.report(D6Input(card.owner, "Flutter Tongue: Roll a D6."), _id)
                roll_count += 1
                if prev_roll is not None and prev_roll + roll == 7:
                    break
                prev_roll = roll

            events: list[Event | Generator] = [
                AVGECardHPChangeEvent(_id, target, 10, AVGEAttributeModifier.SUBSTRACTIVE, CardType.WOODWIND, env)
                for _ in range(roll_count)
            ]
            env.push_packet(Packet(_id, events))
