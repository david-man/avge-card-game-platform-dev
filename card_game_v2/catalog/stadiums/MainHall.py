from __future__ import annotations

from typing import TYPE_CHECKING

from ...avge_abstracts.AVGECard import AVGECard, AVGEStadiumCard, Ability
from ...avge_abstracts.AVGEEventListener import AVGEEventRegulator
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...constants import ActionTypes, EngineGroup, ResponseStatus, default_timeout
from ...core.EventCatalog import TransferCard, PlayNonCharacterCard
from ...core.AVGEIOManager import Notification
from ...engine.event import Event

if TYPE_CHECKING:
    from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ...avge_abstracts.AVGEID import CardID
    from ...constants import User


class MainHall(AVGEStadiumCard):
    '''"Small Ensemble Limit": once active, limits each player to 3 non-character
    plays per round (item/tool/stadium/supporter plays, *and* benching a character
    from hand - v1 counts both toward the same pool despite the "non-character" name),
    starting the round *after* it was played. It cannot be played on the first turn;
    the centralized validator rejects that play before the stadium leaves the hand.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="MainHall",
                description=MainHall.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        def can_play(self, action_card: AVGECard, acting_card: AVGECard) -> bool:
            return acting_card.env.round > 0

        def unavailable_reason(self, action_card: AVGECard, acting_card: AVGECard) -> str:
            return "Main Hall cannot be played on the first turn."

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, MainHall):
                raise TypeError("MainHall action requires its defining card")
            env = acting_card.env
            if env.round == 0:
                await env.report(Notification(
                    acting_card.owner, "MainHall cannot be played on the first turn.", default_timeout,
                ), AVGEEngineID(acting_card, self.action_type, MainHall))
                return
            acting_card.add_listener(_SmallEnsembleLimitRegulator(action_card, env, env.round + 1))



class _SmallEnsembleLimitRegulator(AVGEEventRegulator):
    def __init__(self, owner_card: MainHall, env: AVGEEnvironment, round_active: int):
        super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, MainHall), env, EngineGroup.EXTERNAL_PRECHECK_1)
        self.owner_card = owner_card
        self.round_active = round_active

    def _is_counted_transfer(self, event: TransferCard) -> bool:
        assert not callable(event.deck_from) and not callable(event.deck_to)
        return event.deck_from.deck_type == DeckType.HAND and event.deck_to.deck_type == DeckType.BENCH

    def _count_player_plays_this_round(self, player: User) -> int:
        env = self.env
        count = 0

        index = 0
        while True:
            event, index = env.search_history(PlayNonCharacterCard, None, increment=0, index_to_start=index)
            if event is None:
                break
            index += 1
            assert isinstance(event.id, AVGEEngineID)
            if callable(event.target_card):
                continue
            if event.target_card.owner == player and event.id.calling_action == ActionTypes.PLAYER_CHOICE:
                count += 1

        index = 0
        while True:
            event, index = env.search_history(TransferCard, None, increment=0, index_to_start=index)
            if event is None:
                break
            index += 1
            assert isinstance(event.id, AVGEEngineID)
            if callable(event.card) or callable(event.deck_from) or callable(event.deck_to):
                continue
            if event.card.owner != player or event.id.calling_action != ActionTypes.PLAYER_CHOICE:
                continue
            if self._is_counted_transfer(event):
                count += 1

        return count

    def match(self, event: Event) -> bool:
        if self.owner_card.deck_type != DeckType.STADIUM:
            self.cleanup()
            return False
        if self.env.round < self.round_active:
            return False

        if isinstance(event, PlayNonCharacterCard):
            assert isinstance(event.id, AVGEEngineID)
            if event.id.calling_action != ActionTypes.PLAYER_CHOICE:
                return False
            if callable(event.target_card):
                return False
            player = event.target_card.owner
        elif isinstance(event, TransferCard):
            assert isinstance(event.id, AVGEEngineID)
            if event.id.calling_action != ActionTypes.PLAYER_CHOICE:
                return False
            if callable(event.card) or callable(event.deck_from) or callable(event.deck_to):
                return False
            if not self._is_counted_transfer(event):
                return False
            player = event.card.owner
        else:
            return False

        return self._count_player_plays_this_round(player) >= 3

    async def respond(self, event: Event) -> ResponseStatus:
        # Actor-only: whoever's play/transfer just tripped the round limit - mirrors match()'s
        # own derivation of `player`, since that local doesn't survive into this call.
        assert isinstance(event.id, AVGEEngineID)
        if isinstance(event, PlayNonCharacterCard):
            assert not callable(event.target_card)
            player = event.target_card.owner
        else:
            assert isinstance(event, TransferCard)
            assert not callable(event.card)
            player = event.card.owner
        await self.env.report(Notification(
            player, "Main Hall: Small Ensemble Limit prevented this action!", default_timeout,
        ), event.id)
        return ResponseStatus.REGULATE_FAIL
