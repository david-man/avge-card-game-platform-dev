from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ....avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, Attack, Ability, CardType
from ....avge_abstracts.AVGEEventListener import AVGEEventReactor
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....avge_abstracts.AVGEDeck import DeckType
from ....constants import ActionTypes, EngineGroup, ResponseStatus, AVGEAttributeModifier, default_timeout
from ....engine.event import Event, Generator, Packet
from ....core.EventCatalog import AVGECardHPChangeEvent, PhasePickCard
from ....core.AVGEIOManager import CardSelectionQuery, BroadcastIO

if TYPE_CHECKING:
    from ....avge_abstracts.AVGEID import CardID
    from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ....avge_abstracts.AVGEDeck import AVGEDeck
    from ....constants import User
    from ....core.EventCatalog import TransferCard


class YanwanZhu(AVGECharacterCard):
    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)
        self._heal_reactor: YanwanZhu._StartOfTurnHeal | None = None

    def base_hp(self) -> int:
        return 100

    def base_max_hp(self) -> int:
        return 100

    def base_card_type(self) -> CardType:
        return CardType.CHOIR

    def base_retreat_cost(self) -> int:
        return 1

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {**({ActionTypes.ATK_1: self._IntenseVoice()}), **({ActionTypes.PASSIVE: self._BassBoost()})}


    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        # Entering play is handled globally by TransferCard's own passive-trigger special case.
        entering_play = deck_to.deck_type in (
            DeckType.ACTIVE_CARD, DeckType.BENCH)
        was_in_play = deck_from.deck_type in (
            DeckType.ACTIVE_CARD, DeckType.BENCH)
        if was_in_play and not entering_play and self._heal_reactor is not None:
            self._heal_reactor.cleanup()
            self._heal_reactor = None

    # ------------------------------------------------------------------
    # Listeners
    # ------------------------------------------------------------------

    class _StartOfTurnHeal(AVGEEventReactor):
        '''At the start of Yanwan Zhu's own turn, if she's active with exactly 2 energy, may heal a damaged teammate for 30.'''

        def __init__(self, owner_card: YanwanZhu):
            super().__init__(
                AVGEEngineID(owner_card, ActionTypes.PASSIVE, YanwanZhu),
                owner_card.env,
                EngineGroup.EXTERNAL_REACTORS,
            )
            self.owner_card = owner_card

        def _candidates(self) -> list[AVGECharacterCard]:
            player = self.env.players[self.owner_card.owner]
            return [
                c for pile in (DeckType.ACTIVE_CARD, DeckType.BENCH) for c in player.card_piles[pile]
                if isinstance(c, AVGECharacterCard) and c is not self.owner_card and c.hp < c.max_hp
            ]

        def match(self, event: Event) -> bool:
            if not isinstance(event, PhasePickCard):
                return False
            if self.owner_card.deck_type != DeckType.ACTIVE_CARD:
                return False
            if self.env.turn != self.owner_card.owner:
                return False
            if len(self.owner_card.energy_tokens) != 2:
                return False
            return len(self._candidates()) > 0

        async def react(self, event: Event) -> ResponseStatus | None:
            candidates = self._candidates()
            _id = AVGEEngineID(self.owner_card, ActionTypes.PASSIVE, YanwanZhu)
            chosen = await self.env.report(CardSelectionQuery(
                self.owner_card.owner,
                "Bass Boost: Choose a different character to heal 30 damage (or none).",
                1,
                cast(list[AVGECard], candidates),
                cast(list[AVGECard], candidates),
                True,
                False,
            ), _id)
            if not chosen:
                return None
            target = chosen[0]
            assert isinstance(target, AVGECharacterCard)
            self.env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
                _id,
                target,
                30,
                AVGEAttributeModifier.ADDITIVE,
                CardType.CHOIR,
                self.env,
            )]))
            await self.env.broadcast(BroadcastIO("Bass Boost: Healed for 30", default_timeout))
            return None

    # ------------------------------------------------------------------
    # Abilities
    # ------------------------------------------------------------------

    class _BassBoost(Ability):
        def __init__(self):
            super().__init__(
                name="Bass Boost",
                description="At the start of your turn, if Yanwan Zhu is active with exactly 2 energy, heal a different damaged character on your team for 30.",
                action_type=ActionTypes.PASSIVE,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = action_card
            assert isinstance(card, YanwanZhu)
            if card._heal_reactor is None:
                card._heal_reactor = YanwanZhu._StartOfTurnHeal(card)
                card.add_listener(card._heal_reactor)

    # ------------------------------------------------------------------
    # Attacks
    # ------------------------------------------------------------------

    class _IntenseVoice(Attack):
        def __init__(self):
            super().__init__(
                name="Intense Voice",
                description="Deal 60 damage to the opposing active character, and 10 damage to each of the opponent's benched characters.",
                action_type=ActionTypes.ATK_1,
                cost=3,
            )

        async def __call__(self, action_card: AVGECard, acting_card: AVGECard) -> None:
            card = acting_card
            assert isinstance(card, AVGECharacterCard)
            env = card.env
            opponent = env.get_opponent(card.owner)
            target = env.get_player_active(opponent)
            _id = AVGEEngineID(card, self.action_type, YanwanZhu)

            events: list[Event | Generator] = [
                AVGECardHPChangeEvent(
                    _id,
                    target,
                    60,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.CHOIR,
                    env,
                )
            ]
            opponent_bench = [c for c in opponent.card_piles[DeckType.BENCH] if isinstance(
                c, AVGECharacterCard)]
            for bench_card in opponent_bench:
                events.append(AVGECardHPChangeEvent(
                    _id,
                    bench_card,
                    10,
                    AVGEAttributeModifier.SUBSTRACTIVE,
                    CardType.CHOIR,
                    env,
                ))

            env.push_packet(Packet(_id, events))
