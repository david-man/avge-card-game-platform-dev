from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ...avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, AVGESupporterCard, Ability
from ...avge_abstracts.AVGEEventListener import AVGEEventRegulator
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...constants import ActionTypes, EngineGroup, ResponseStatus, User, default_timeout
from ...core.EventCatalog import TransferCard
from ...core.AVGEIOManager import CardSelectionQuery, Notification
from ...engine.event import Event, Packet

if TYPE_CHECKING:
    from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment


class Emma(AVGESupporterCard):
    '''Forces the opponent to swap in a benched character you choose, then locks
    *that* character from retreating during the opponent's next turn (the only turn
    they'd actually get a chance to try) - the one "one-shot" supporter that isn't
    actually one-shot, since it leaves a persistent regulator behind.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="Emma",
                description=Emma.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, Emma):
                raise TypeError("Emma action requires its defining card")
            env = acting_card.env
            opponent = env.get_opponent(acting_card.owner)
            opponent_active_pile = opponent.card_piles[DeckType.ACTIVE_CARD]
            opponent_bench = opponent.card_piles[DeckType.BENCH]
            _id = AVGEEngineID(acting_card, self.action_type, Emma)

            bench_candidates: list[AVGECharacterCard] = [
                c for c in opponent_bench.cards_holding if isinstance(c, AVGECharacterCard)
            ]
            if not bench_candidates:
                await env.report(Notification(
                    acting_card.owner, "Opponent has no benched character to switch with.", default_timeout,
                ), _id)
                return

            picked = await env.report(CardSelectionQuery(
                acting_card.owner,
                "Emma: Choose one of the opponent's benched characters to force into active.",
                1,
                cast(list[AVGECard], bench_candidates),
                cast(list[AVGECard], bench_candidates),
                False,
                False,
            ), _id)
            locked_character = picked[0]
            assert isinstance(locked_character, AVGECharacterCard)

            opponent_active = env.get_player_active(opponent)
            round_active = env.round + 1
            acting_card.add_listener(_NextTurnSwapLockRegulator(action_card, env, locked_character, opponent.id, round_active))

            env.push_packet(Packet(_id, [
                TransferCard(_id, locked_character, opponent_bench, opponent_active_pile, env),
                TransferCard(_id, opponent_active, opponent_active_pile, opponent_bench, env),
            ]))



class _NextTurnSwapLockRegulator(AVGEEventRegulator):
    def __init__(self, owner_card: Emma, env: AVGEEnvironment, locked_character: AVGECharacterCard, opponent: User, round_active: int):
        super().__init__(AVGEEngineID(owner_card, ActionTypes.NONCHAR, Emma), env, EngineGroup.EXTERNAL_PRECHECK_1)
        self.owner_card = owner_card
        self.locked_character = locked_character
        self.opponent = opponent
        self.round_active = round_active

    def match(self, event: Event) -> bool:
        if self.env.round > self.round_active:
            self.cleanup()
            return False
        if not isinstance(event, TransferCard):
            return False
        assert isinstance(event.id, AVGEEngineID)
        if callable(event.card) or callable(event.deck_from) or callable(event.deck_to):
            return False
        if event.id.calling_action != ActionTypes.PLAYER_CHOICE:
            return False
        if event.deck_from.deck_type != DeckType.ACTIVE_CARD or event.deck_to.deck_type != DeckType.BENCH:
            return False
        if event.card is not self.locked_character:
            return False
        if event.card.owner != self.opponent:
            return False
        return self.env.round == self.round_active

    async def respond(self, event: Event) -> ResponseStatus:
        # Actor-only: whoever's attempted retreat just got blocked - the opponent of Emma's own
        # owner, already tracked as self.opponent.
        assert isinstance(event.id, AVGEEngineID)
        await self.env.report(Notification(
            self.opponent, "Emma: this character cannot retreat this turn.", default_timeout,
        ), event.id)
        return ResponseStatus.REGULATE_FAIL
