from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ...avge_abstracts.AVGECard import AVGEItemCard, AVGECard, AVGEStadiumCard, Ability
from ...avge_abstracts.AVGEDeck import AVGEDeck, DeckType
from ...avge_abstracts.AVGEEventListener import AVGEEventRegulator
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes, EngineGroup, ResponseStatus, default_timeout
from ...core.EventCatalog import TransferCard
from ...core.AVGEIOManager import CardSelectionQuery, Notification
from ...engine.event import Event, Generator, Packet

if TYPE_CHECKING:
    from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment


class BAIEmail(AVGEItemCard):
    '''Discard the active stadium (if any), then optionally search your deck for a
    stadium to add to hand; either way, locks out ANY player from playing a stadium
    until the owner's own next turn.

    Unlike AVGEBirb's curse, this round-scoped lock isn't the same bug pattern: it's
    global (v1's assessor has no per-player restriction on who is blocked), so
    `round_until = env.round + 2` (the round when it's next the OWNER's own turn again)
    is a well-defined window - through the rest of this turn, the opponent's whole next
    turn, and the owner's own following turn - not a condition that can never be
    satisfied like AVGEBirb's was. `+ 2` is hardcoded rather than a general
    `get_next_turn()` re-derivation because it's only ever computed here, at play time,
    when it's necessarily the owner's own turn (items are only played on your turn).

    Blocked at the `TransferCard` level (`deck_to.deck_type == STADIUM`), not on
    `PlayNonCharacterCard` like v1's assessor. Phase2's stadium dispatch
    (`Phase2CardMovement`) is the *only* way a stadium card ever enters
    `env.stadium_cardholder` - `TransferCard.act()`'s own "Special Case 3" is what
    triggers `PlayNonCharacterCard` for a stadium, always as a direct consequence of
    that same transfer - so gating the transfer itself is both the sole gate point that
    exists and the cleaner one: it stops the card from ever leaving hand, instead of
    letting it move and then only cancelling the follow-on play effect.'''

    async def on_transfer(self, deck_from: AVGEDeck, deck_to: AVGEDeck, transfer_event: TransferCard) -> None:
        return

    def base_actions(self) -> dict[ActionTypes, Ability]:
        return {ActionTypes.NONCHAR: self._PlayAction()}

    class _PlayAction(Ability):
        def __init__(self):
            super().__init__(
                name="BAIEmail",
                description=BAIEmail.__doc__ or "",
                action_type=ActionTypes.NONCHAR,
            )

        async def __call__(
            self, action_card: AVGECard, acting_card: AVGECard,
        ) -> None:
            if not isinstance(action_card, BAIEmail):
                raise TypeError("BAIEmail action requires its defining card")
            env = acting_card.env
            player = env.players[acting_card.owner]
            deck = player.card_piles[DeckType.DECK]
            hand = player.card_piles[DeckType.HAND]

            _id = AVGEEngineID(acting_card, self.action_type, BAIEmail)
            events: list[Event | Generator] = []

            if len(env.stadium_cardholder) > 0:
                active_stadium = env.stadium_cardholder.cards_holding[0]
                assert isinstance(active_stadium, AVGEStadiumCard)
                discard_owner = env.players[active_stadium.owner]
                events.append(TransferCard(
                    _id, active_stadium, env.stadium_cardholder, discard_owner.card_piles[DeckType.DISCARD], env,
                ))

            stadiums_in_deck = [c for c in deck.cards_holding if isinstance(c, AVGEStadiumCard)]
            if stadiums_in_deck:
                picked = await env.report(CardSelectionQuery(
                    acting_card.owner,
                    "BAIEmail: Choose a Stadium from your deck to put into your hand.",
                    1,
                    cast(list[AVGECard], stadiums_in_deck),
                    list(deck.cards_holding),
                    True,
                    False,
                ), _id)
                if picked:
                    events.append(TransferCard(_id, picked[0], deck, hand, env))

            acting_card.add_listener(BAIEmail._StadiumPlayLock(env.round + 2, env))
            if events:
                env.push_packet(Packet(_id, events))


    class _StadiumPlayLock(AVGEEventRegulator):
        def __init__(self, round_until: int, env: AVGEEnvironment):
            super().__init__(AVGEEngineID(None, ActionTypes.NONCHAR, BAIEmail), env, EngineGroup.EXTERNAL_PRECHECK_1)
            self.round_until = round_until

        def match(self, event: Event) -> bool:
            if self.env.round > self.round_until:
                self.cleanup()
                return False
            if not isinstance(event, TransferCard):
                return False
            if callable(event.deck_to):
                return False
            return event.deck_to.deck_type == DeckType.STADIUM

        async def respond(self, event: Event) -> ResponseStatus:
            assert isinstance(event, TransferCard)
            assert not callable(event.card)
            assert isinstance(event.id, AVGEEngineID)
            # Actor-only: the person whose stadium play just got blocked, not necessarily
            # BAIEmail's own owner - this lock applies to both players.
            await self.env.report(Notification(
                event.card.owner, "BAIEmail: Stadium cards cannot be played right now.", default_timeout,
            ), event.id)
            if event.id.calling_action == ActionTypes.PLAYER_CHOICE:
                return ResponseStatus.REGULATE_FAIL
            return ResponseStatus.REGULATE_IGNORE
