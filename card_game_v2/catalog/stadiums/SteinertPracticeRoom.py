from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ...avge_abstracts.AVGECard import AVGECard, AVGECharacterCard, AVGEStadiumCard, Ability
from ...avge_abstracts.AVGEEventListener import AVGEEventModifier, AVGEEventRegulator
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...constants import ActionTypes, EngineGroup, ResponseStatus, default_timeout
from ...core.EventCatalog import TransferCard, PlayCharacterCard
from ...core.AVGEIOManager import CardSelectionQuery, BroadcastIO, Notification
from ...engine.event import Event, Generator, Packet

if TYPE_CHECKING:
    from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
    from ...avge_abstracts.AVGEID import CardID
    from ...constants import User


class SteinertPracticeRoom(AVGEStadiumCard):
    '''"Practice Prison": on play, forces both players (owner first, then opponent) to
    discard benched characters down to 2, then permanently caps everyone's bench at 2
    and adds +1 energy cost to every ATK_1/ATK_2 (regardless of who/what triggered it -
    confirmed against v1 source, this modifier has no `PLAYER_CHOICE` gate, unlike
    SteinertBasement's otherwise-identical cost modifier, so a borrowed/forced attack
    still gets the surcharge here). The NONCHAR action being a single async coroutine
    lets the two sequential discard-selections just `await` in a row, dramatically
    simpler than v1's cache-based re-entrant resolution. See SteinertBasement's
    `_AttackExtraCostModifier` docstring for the DemiLu constrainer-compatibility note
    that applies equally to this file's `_AttackExtraCostModifier`.'''

    def __init__(self, cardID: CardID, env: AVGEEnvironment, owner: User, deck_in: DeckType):
        super().__init__(cardID, env, owner, deck_in)

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="SteinertPracticeRoom",
                description=SteinertPracticeRoom.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, SteinertPracticeRoom):
                raise TypeError("SteinertPracticeRoom action requires its defining card")
            env = acting_card.env
            owner_player = env.players[acting_card.owner]
            opponent_player = env.get_opponent(acting_card.owner)
            _id = AVGEEngineID(acting_card, self.action_type, SteinertPracticeRoom)

            for target_player in (owner_player, opponent_player):
                bench: list[AVGECharacterCard] = [
                    c for c in target_player.card_piles[DeckType.BENCH] if isinstance(c, AVGECharacterCard)
                ]
                extra = max(0, len(bench) - 2)
                if extra == 0:
                    continue

                picked = await env.report(CardSelectionQuery(
                    target_player.id,
                    "Steinert Practice Room: Choose benched character(s) to discard down to 2.",
                    extra,
                    cast(list[AVGECard], bench),
                    cast(list[AVGECard], bench),
                    False,
                    False,
                ), _id)

                events: list[Event | Generator] = [
                    TransferCard(_id, chosen, target_player.card_piles[DeckType.BENCH], target_player.card_piles[DeckType.DISCARD], env)
                    for chosen in picked
                ]
                if events:
                    env.push_packet(Packet(_id, events))

            acting_card.add_listener(_BenchCapRegulator(action_card, env))
            acting_card.add_listener(_AttackExtraCostModifier(action_card, env))



class _BenchCapRegulator(AVGEEventRegulator):
    def __init__(self, owner_card: SteinertPracticeRoom, env: AVGEEnvironment):
        super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, SteinertPracticeRoom), env, EngineGroup.EXTERNAL_PRECHECK_1)
        self.owner_card = owner_card

    def match(self, event: Event) -> bool:
        if self.owner_card.deck_type != DeckType.STADIUM:
            self.cleanup()
            return False
        if not isinstance(event, TransferCard):
            return False
        assert isinstance(event.id, AVGEEngineID)
        if callable(event.deck_to):
            return False
        if event.id.calling_action != ActionTypes.PLAYER_CHOICE:
            return False
        if event.deck_to.deck_type != DeckType.BENCH:
            return False
        return len(event.deck_to.cards_holding) >= 2

    async def respond(self, event: Event) -> ResponseStatus:
        assert isinstance(event, TransferCard)
        assert not callable(event.card)
        assert isinstance(event.id, AVGEEngineID)
        await self.env.report(Notification(
            event.card.owner,
            "Steinert Practice Room: Practice Prison prevented this action!", default_timeout,
        ), event.id)
        return ResponseStatus.REGULATE_FAIL


class _AttackExtraCostModifier(AVGEEventModifier):
    def __init__(self, owner_card: SteinertPracticeRoom, env: AVGEEnvironment):
        super().__init__(AVGEEngineID(owner_card, ActionTypes.PASSIVE, SteinertPracticeRoom), env, EngineGroup.EXTERNAL_MODIFIERS_1)
        self.owner_card = owner_card

    def match(self, event: Event) -> bool:
        if self.owner_card.deck_type != DeckType.STADIUM:
            self.cleanup()
            return False
        if not isinstance(event, PlayCharacterCard):
            return False
        if callable(event.target_card) or callable(event.action) or callable(event.cost):
            return False
        return event.action in (ActionTypes.ATK_1, ActionTypes.ATK_2)

    async def modify(self, event: Event) -> None:
        assert isinstance(event, PlayCharacterCard)
        assert not callable(event.cost)
        event.cost += 1
        await self.env.broadcast(BroadcastIO("Steinert Practice Room: 15 Minute Walk increased the energy cost", default_timeout))
