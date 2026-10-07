from __future__ import annotations

import random
from typing import TYPE_CHECKING, cast

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventReactor
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ....constants import ActionTypes, EngineGroup, AVGEAttributeModifier, User, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, TransferCard
from ....core.AVGEIOManager import CardSelectionQuery, StringSelectionQuery, CoinflipData, BroadcastIO, Notification

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEID import CardID


class GabrielChen(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._threshold_reactor: GabrielChen._ThresholdReactor | None = None

    def base_hp(self) -> int:
        return 90

    def base_max_hp(self) -> int:
        return 90

    def base_card_type(self) -> CardType:
        return CardType.STRING

    def base_retreat_cost(self) -> int:
        return 2

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_2: self._Harmonics()}), **({ActionTypes.PASSIVE: self._YouKnowWhatItIsPassive()})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    class _YouKnowWhatItIsPassive(Ability):
        def __init__(self):
            super().__init__(
                name="You Know What It Is",
                description="The first time your HP drops to 60 or less, may deal 70 damage to a random opposing character.",
                action_type=ActionTypes.PASSIVE,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = action_card
            assert isinstance(card, GabrielChen)
            if card._threshold_reactor is None:
                card._threshold_reactor = GabrielChen._ThresholdReactor(card, card.env)
                card.add_listener(card._threshold_reactor)

    class _ThresholdReactor(AVGEEventReactor):
        '''Fires (once) the first time a matching AVGECardHPChange leaves the owner
        at or below 60 HP (an absolute threshold, not 60% of max HP). Stays registered
        forever if answered "Yes" while the opponent has no characters in play (no v1
        cleanup() call on that path either) - matches v1 exactly, not a bug.'''

        def __init__(self, owner_card: GabrielChen, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, GabrielChen), env, EngineGroup.EXTERNAL_REACTORS)
            self.owner_card = owner_card

        def match(self, event: Event) -> bool:
            if not isinstance(event, AVGECardHPChangeEvent):
                return False
            if callable(event.target_card):
                return False
            if event.target_card is not self.owner_card:
                return False
            if self.owner_card.deck_type not in (DeckType.ACTIVE_CARD, DeckType.BENCH):
                return False
            return self.owner_card.hp <= 60

        async def react(self, event: Event) -> None:
            owner = self.owner_card
            env = self.env
            _id = AVGEEngineID(owner, ActionTypes.PASSIVE, GabrielChen)

            choice = await env.report(StringSelectionQuery(
                owner.owner,
                "You Know What It Is: Deal 70 damage to one random opposing character?",
                1,
                ["Yes", "No"],
                ["Yes", "No"],
                False,
                False,
            ), _id)
            if choice[0] != "Yes":
                self.cleanup()
                return

            opponent = env.get_opponent(owner.owner)
            targets: list[AVGECharacterCard] = [
                c for c in opponent.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
            ] + [
                c for c in opponent.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
            ]
            if not targets:
                return

            target = random.choice(targets)
            self.cleanup()
            await env.broadcast(BroadcastIO("You Know What It Is: Dealt 70 damage to a random opposing character.", default_timeout))
            event.push_event([AVGECardHPChangeEvent(
                _id, target, 70, AVGEAttributeModifier.SUBSTRACTIVE, CardType.STRING, env,
            )])

    class _Harmonics(Attack):
        def __init__(self):
            super().__init__(
                name="Harmonics",
                description="Flip 2 coins. If both are heads, choose to deal 60 damage to 3 opposing characters, or 70 damage to 2.",
                action_type=ActionTypes.ATK_2,
                cost=2,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            _id = AVGEEngineID(card, self.action_type, GabrielChen)

            heads = 0
            for _ in range(2):
                heads += await env.report(CoinflipData(card.owner, "Harmonics: Flip 2 coins."), _id)
            if heads != 2:
                await env.report(Notification(
                    card.owner,
                    f"{card} used Harmonics, but they didn't roll both heads...", default_timeout,
                ), _id)
                return

            mode_options = ["Deal 60 to three opposing characters", "Deal 70 to two opposing characters"]
            mode = (await env.report(StringSelectionQuery(
                card.owner,
                "Harmonics: Choose one effect.",
                1,
                mode_options,
                mode_options,
                False,
                False,
            ), _id))[0]

            opponent = env.get_opponent(card.owner)
            targets: list[AVGECharacterCard] = [
                c for c in opponent.card_piles[DeckType.ACTIVE_CARD] if isinstance(c, AVGECharacterCard)
            ] + [
                c for c in opponent.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
            ]
            req_count = 3 if mode == mode_options[0] else 2
            count = min(req_count, len(targets))
            if count == 0:
                return

            chosen = await env.report(CardSelectionQuery(
                card.owner,
                "Harmonics: Choose opposing targets.",
                count,
                cast(list[AVGECard], targets),
                cast(list[AVGECard], targets),
                False,
                False,
            ), _id)

            dmg_amt = 60 if mode == mode_options[0] else 70
            events: list[Event | Generator] = []
            for tgt in chosen:
                assert isinstance(tgt, AVGECharacterCard)
                events.append(AVGECardHPChangeEvent(
                    _id, tgt, dmg_amt, AVGEAttributeModifier.SUBSTRACTIVE, CardType.STRING, env,
                ))
            env.push_packet(Packet(_id, events))
