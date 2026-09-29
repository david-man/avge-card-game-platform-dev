from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Literal, Protocol

from ..avge_abstracts.AVGECard import AVGECard
from ..avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ..avge_abstracts.AVGEID import AVGEEngineID
from ..constants import ActionTypes, User, WinReasons
from ..core.EventCatalog import PhasePickCard
from ..engine.event import Packet
from . import config
from . import game_setup
from . import match_log
from .decks import build_preset_decks
from .io_adapter import NetworkIO
from .listeners import default_core_listeners

logger = logging.getLogger(__name__)

ForceEndReason = Literal["concede", "disconnect_timeout"]

_REASON_TO_WIN_REASON: dict[str, WinReasons] = {
    "concede": WinReasons.CONCEDE,
    "disconnect_timeout": WinReasons.DISCONNECT_TIMEOUT,
}


class Transport(Protocol):
    '''Minimal duck-typed interface a real transport (FastAPI's WebSocket) or a test stub must
    satisfy - GameSession never depends on a concrete WebSocket type.'''
    async def send_json(self, data: dict[str, Any]) -> None: ...
    async def close(self) -> None: ...


async def safe_send(transport: Transport, data: dict[str, Any]) -> None:
    '''Best-effort send that swallows any transport failure - shared by matchmaker.py and
    ws_routes.py, both of which send notices to sockets that may already be gone (a superseded
    login, a connection that dropped between message and send).'''
    try:
        await transport.send_json(data)
    except Exception:
        pass


class PlayerSeat:
    def __init__(self, user: User):
        self.user = user
        self.account_id: str | None = None
        # Display name of the account in this seat (Account.username), for clients to show who is
        # who - the engine itself only knows PLAYER_1/PLAYER_2.
        self.username: str | None = None
        self.websocket: Transport | None = None
        self.connected = False
        self.disconnect_task: asyncio.Task[None] | None = None
        # Distinct from `connected`: stays True forever once attach() has been called at least
        # once, even after a later detach(). Lets detach() tell "a real opponent was here and is
        # now also gone" (a match both players abandoned) apart from "no opponent has ever been
        # paired into this seat yet" (the matchmaker's lone waiting occupant) - see detach().
        self.ever_attached = False
        # The account's own selected/resolved deck (server/decks.py's build_game_deck output),
        # set by Matchmaker.join() once that account's deck is known. None until then - see
        # GameSession.configure_decks(), which requires both seats' decks to be set first.
        self.deck: list[type[AVGECard]] | None = None


class GameSession:
    '''Owns one AVGEEnvironment, its NetworkIO, the running env.run() task, and both players'
    connection state (PlayerSeat). `on_finished` is called exactly once, when the session should
    be torn down (natural GameEnd, a forced ending, or both-players-abandoned) - the matchmaker
    uses it to deregister the session from its own tables.'''

    def __init__(self, game_id: str, on_finished: Callable[[str], None]):
        self.id = game_id
        self._on_finished = on_finished
        self.seats: dict[User, PlayerSeat] = {user: PlayerSeat(user) for user in User}
        self.io = NetworkIO(self._send_to_user, self._on_transport_failure)
        # A throwaway placeholder, not a real game's deck - AVGEEnvironment.__init__ is a heavy
        # constructor that needs both players' full card lists simultaneously, but Matchmaker.
        # join() only learns the second player's chosen deck well after this session already
        # exists (PLAYER_1's own join constructs it, before any opponent exists to pair with).
        # configure_decks() below replaces this outright with a real one once both seats' decks
        # are known - kept here, rather than leaving self.env unset until then, purely so the many
        # tests (and code paths like force_end()/_abandon()) that construct/act on a GameSession
        # without ever calling prepare() still have a real, non-None self.env to work with.
        self.env = AVGEEnvironment(self.io, build_preset_decks(), default_core_listeners())
        self.task: asyncio.Task[None] | None = None
        self.finished = False
        self._lifecycle: list[dict[str, Any]] = []

    def configure_decks(self) -> None:
        '''Replaces the placeholder self.env with a real one built from both seats' resolved
        decks (PlayerSeat.deck, set by Matchmaker.join()) - must be called after both are set and
        before prepare()/begin_running(). Replacement, not mutation: AVGEEnvironment.__init__
        builds self.cache from the complete card list at construction time, so swapping card
        objects into an already-built environment would leave the cache silently stale.
        self.io.register_to_environment() (core/AVGEIOManager.py) is a plain re-point with no
        per-env state to migrate, so rebuilding is safe even though self.io itself isn't rebuilt.
        Note this also re-rolls env.turn (who goes first, AVGEEnvironment.__init__) - harmless,
        and arguably more correct once both real decks are actually known.'''
        decks: dict[User, list[type[AVGECard]]] = {}
        for user, seat in self.seats.items():
            assert seat.deck is not None, f"{user.name} has no deck configured"
            decks[user] = seat.deck
        assert self.task is None and not self.finished, \
            "configure_decks() must run before the game starts, not on a running/finished session"
        self.env = AVGEEnvironment(self.io, decks, default_core_listeners())

    def _log_lifecycle(self, kind: str, **fields: Any) -> None:
        entry : dict[str, Any] = {"ts": time.time(), "kind": kind, **fields}
        self._lifecycle.append(entry)
        logger.info("%s: %s", kind, fields)

    async def _send_to_user(self, user: User, message: dict[str, Any]) -> None:
        seat = self.seats[user]
        if seat.websocket is None or not seat.connected:
            raise ConnectionError(f"{user} is not currently connected")
        await seat.websocket.send_json(message)

    async def _on_transport_failure(self, user: User) -> None:
        self.detach(user, self.seats[user].websocket)

    # --- Lifecycle ---

    async def prepare(self) -> None:
        '''Deals hands and queues the opening packet, but does NOT start the engine running yet -
        callers that need to notify both clients before any event traffic can arrive (ws_routes.py,
        to guarantee game_start is the first substantive message either socket sees) call this and
        begin_running() separately. start() below is a same-effect convenience for callers (mostly
        tests) that don't care about that ordering.'''
        await game_setup.perform_initial_setup(self.env, extra_on_packet_failed=self._log_packet_rejection)
        _id = AVGEEngineID(None, ActionTypes.ENV, None)
        self.env.push_packet(Packet(_id, [PhasePickCard(_id, self.env)]))

    async def _log_packet_rejection(self, packet: Packet) -> None:
        '''Passed into game_setup.perform_initial_setup() as extra_on_packet_failed, so it runs
        composed alongside the ActionRejectedUpdate broadcast rather than wrapping it on after the
        fact - REGULATE_FAIL'd packets are otherwise invisible to env.engine.history
        (Engine.flush() discards their pending records), so this records the rejection into the
        session's own lifecycle log.'''
        # packet.event_log holds whatever in this packet already committed before the failure;
        # packet.current_event is the one that triggered REGULATE_FAIL (there is no plain "all
        # events in this packet" attribute - the rest of the queue is private).
        committed = [type(e).__name__ for e in packet.event_log]
        failing = [type(packet.current_event).__name__] if packet.current_event is not None else []
        self._log_lifecycle(
            "packet_rejected", for_user=self.env.turn.name,
            committed_before_failure=committed, failed_on=failing,
        )

    def begin_running(self) -> None:
        self._arm_grace_timers_for_already_disconnected_seats()
        self.task = asyncio.create_task(self._run_wrapper())

    def _arm_grace_timers_for_already_disconnected_seats(self) -> None:
        '''A seat can already be disconnected the moment the game actually starts running - e.g.
        the originally-queued player vanished before an opponent ever paired with them
        (Matchmaker.join() doesn't require the waiting seat to still be connected to pair a second
        player into it). detach() itself is a no-op for a seat that's already disconnected - so
        without this, that seat's absence would never be tracked at all, leaving the connected
        opponent stuck forever with no forced-win path (or, if both seats are already gone, the
        session leaking forever with no cleanup path). Mirrors exactly what detach() would have
        done had the disconnection happened right now instead of before the game started.'''
        if all(not seat.connected for seat in self.seats.values()):
            # Both already gone before the game even started running - same immediate-abandon
            # path detach() takes; nobody to notify, nobody worth waiting on.
            asyncio.create_task(self._abandon())
            return
        for user, seat in self.seats.items():
            other = self.seats[user.next]
            if not seat.connected and seat.disconnect_task is None and other.connected:
                seat.disconnect_task = asyncio.create_task(self._disconnect_grace(user))
                asyncio.create_task(self._notify_disconnected(other))

    async def start(self) -> None:
        await self.prepare()
        self.begin_running()

    async def _run_wrapper(self) -> None:
        try:
            await self.env.run()
        except asyncio.CancelledError:
            return
        except Exception as exc:
            await self._fail(exc)
            return
        # The engine loop only exits on its own when a real GameEnd fires (terminate_flag) or the
        # packet queue empties - either way, the game is over and the session should be torn down.
        if not self.finished:
            self.finished = True
            self._log_lifecycle(
                "completed_naturally",
                winner=self.env.winner.name if self.env.winner is not None else None,
                reason=self.env.win_reason.value if self.env.win_reason is not None else None,
            )
            self._cancel_all_timers()
            await self._finish()

    async def _fail(self, exc: BaseException) -> None:
        '''A bug anywhere in the engine's own execution (card logic, IO payload-building, etc.)
        propagates out of env.run() unhandled by default - without this, the session would leak
        forever (never deregistered) and both players would be left hanging indefinitely with no
        game_over, no error, nothing. This is the safety net: log the full traceback, kick both
        connected players out with a clear explanation, and clean up exactly like any other
        forced ending.'''
        if self.finished:
            return
        self.finished = True
        logger.exception("Unhandled exception in game engine for session %s", self.id, exc_info=exc)
        self._log_lifecycle("fatal_error", detail=f"{type(exc).__name__}: {exc}")

        message : dict[str, str | None] = {"type": "game_over", "winner": None, "reason": "server_error"}
        for seat in self.seats.values():
            if seat.connected and seat.websocket is not None:
                await safe_send(seat.websocket, message)

        # No _cancel_task() here - _fail() runs from inside _run_wrapper, which IS self.task's
        # own coroutine; self.task.cancel(); await self.task would mean awaiting itself (a
        # deadlock). Returning from _fail() lets _run_wrapper() complete naturally instead.
        self._cancel_all_timers()
        await self._finish()

    # --- Connection state ---

    def usernames(self) -> dict[str, str]:
        '''Seat name -> display name for both seats (the seat name itself if nobody's been
        seated there yet).'''
        return {user.name: seat.username or user.name for user, seat in self.seats.items()}

    def attach(self, user: User, websocket: Transport) -> bool:
        '''Returns False (and does nothing else) if the session has already finished - force_end/
        _fail/_abandon set self.finished immediately but only deregister the session from the
        matchmaker's tables several awaits later (after sending game_over to connected seats and
        awaiting the cancelled engine task), so a reconnect can land in that gap and otherwise
        find_active_game() would still hand the caller a session that's already mid-teardown.
        Without this guard, attach() would happily rebind the socket to a session whose game_over
        broadcast list was already built without it - wedging that client permanently, with no
        error and no game_over ever arriving.'''
        if self.finished:
            return False
        seat = self.seats[user]
        self._log_lifecycle("attach", user=user.name, reconnect=seat.disconnect_task is not None)
        seat.websocket = websocket
        seat.connected = True
        seat.ever_attached = True
        if seat.disconnect_task is not None:
            seat.disconnect_task.cancel()
            seat.disconnect_task = None
        # No _both_disconnected_task to cancel here anymore - both-disconnected abandonment is now
        # scheduled immediately (detach()) rather than via a long-running cancellable timer, and
        # _abandon() itself re-checks connection state at execution time to cover a reconnect
        # landing in that scheduling gap.
        return True

    def detach(self, user: User, websocket: Transport | None) -> None:
        '''`websocket` must be the specific connection being detached, not just "whichever one is
        currently attached" - a stale connection's belated disconnect notification (e.g. one just
        superseded by a newer login for the same account) must not silently disconnect a seat
        that's already been reclaimed by a different, newer connection. Mirrors the identical
        identity guard in Matchmaker.release().'''
        seat = self.seats[user]
        if not seat.connected or seat.websocket is not websocket:
            return
        self._log_lifecycle("detach", user=user.name)
        seat.connected = False
        seat.websocket = None
        if self.finished:
            return
        other = self.seats[user.next]
        if not other.connected:
            if other.ever_attached:
                # Both seats gone now, and `other` was a real occupant (not just an empty seat
                # nobody has paired into yet) - abandon immediately rather than waiting out a
                # grace period; this also cancels (via _cancel_all_timers() inside _abandon())
                # whatever _disconnect_grace timer might still be running for `other` from when it
                # disconnected first, so the earlier disconnector never gets awarded a win just for
                # going first.
                asyncio.create_task(self._abandon())
            # else: `other` has never been attached at all - this is the matchmaker's lone waiting
            # occupant vanishing before anyone paired with them, not "both players abandoned a
            # match". Leave the session in place so a second player can still pair into it later
            # (see test_begin_running_arms_a_grace_timer_for_a_seat_already_disconnected_before_start).
        else:
            seat.disconnect_task = asyncio.create_task(self._disconnect_grace(user))
            asyncio.create_task(self._notify_disconnected(other))

    async def _notify_disconnected(self, seat: PlayerSeat) -> None:
        if seat.websocket is None:
            return
        try:
            await seat.websocket.send_json(
                {"type": "opponent_disconnected", "grace_seconds": config.RECONNECT_GRACE_SECONDS},
            )
        except Exception:
            pass

    async def _disconnect_grace(self, user: User) -> None:
        try:
            await asyncio.sleep(config.RECONNECT_GRACE_SECONDS)
        except asyncio.CancelledError:
            return
        seat = self.seats[user]
        if seat.connected or self.finished:
            return
        # This coroutine IS seat.disconnect_task - clear the reference before calling
        # force_end()/_abandon() below, both of which call _cancel_all_timers(), which would
        # otherwise call .cancel() on the very task currently running this code. That
        # self-cancellation used to be harmless (force_end/_abandon/_finish had no await points
        # between the cancel and completion, so it never got a chance to actually be delivered)
        # but _finish()'s awaited match-log write now gives it one, which would otherwise abort
        # this task before self._on_finished() ever ran.
        seat.disconnect_task = None
        if not self.seats[user.next].connected:
            # Defensive fallback, not the primary mechanism: both-disconnect abandonment is now
            # triggered immediately from detach() the moment the second player disconnects (which
            # also cancels this very timer via _cancel_all_timers()), so in the normal case this
            # branch should be unreachable - the opponent's own detach() will have already called
            # _abandon() and cancelled this task before its sleep could ever complete with the
            # opponent still gone. Kept as a safety net anyway: this exact race (whichever seat
            # disconnected first "winning" by default even though both are equally absent) has
            # bitten this codebase once already (see the regression test in test_session.py).
            await self._abandon()
            return
        await self.force_end(winner=user.next, reason="disconnect_timeout")

    async def _abandon(self) -> None:
        '''Both players gone - clean up with no winner declared; nobody is left connected to
        receive a game_over message anyway. Callers that schedule this via asyncio.create_task()
        (detach(), _arm_grace_timers_for_already_disconnected_seats()) leave a real scheduling gap
        between "both were disconnected" and this actually running - re-checking connection state
        here (not just self.finished) covers a reconnect landing in that gap, the same way
        _disconnect_grace()'s own pre-flight check does for its call path.'''
        if self.finished or any(seat.connected for seat in self.seats.values()):
            return
        self.finished = True
        self._log_lifecycle("abandoned")
        self._cancel_all_timers()
        await self._cancel_task()
        await self._finish()

    async def force_end(self, winner: User, reason: ForceEndReason) -> None:
        if self.finished:
            return
        self.finished = True
        self._log_lifecycle("forced_end", winner=winner.name, reason=reason)
        self.env.winner = winner
        self.env.win_reason = _REASON_TO_WIN_REASON[reason]

        message = {"type": "game_over", "winner": winner.name, "reason": reason}
        for seat in self.seats.values():
            if seat.connected and seat.websocket is not None:
                await safe_send(seat.websocket, message)

        self._cancel_all_timers()
        await self._cancel_task()
        await self._finish()

    async def _cancel_task(self) -> None:
        if self.task is not None:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    def _cancel_all_timers(self) -> None:
        for seat in self.seats.values():
            if seat.disconnect_task is not None:
                seat.disconnect_task.cancel()
                seat.disconnect_task = None
        self.io.cancel_backstops()

    # --- Termination ---

    async def _finish(self) -> None:
        '''The single point every termination path (natural completion, force_end, _abandon,
        _fail) funnels through, so the match log gets written exactly once regardless of how the
        game ended.'''
        await self._write_match_log()
        self._on_finished(self.id)

    async def _write_match_log(self) -> None:
        # Wrapped in its own try/except so a bug in logging can never prevent session
        # cleanup/deregistration from completing. The payload dict is built here on the event
        # loop (serialize_history_records() is CPU-bound dict construction, not I/O) - only the
        # actual disk write is offloaded, since that's what can otherwise stall every other
        # concurrent match's websocket I/O for its duration.
        try:
            payload : dict[str, Any] = {
                "game_id": self.id,
                "ended_at": time.time(),
                "lifecycle": self._lifecycle,
                "records": match_log.serialize_history_records(self.env, self.io),
            }
            await asyncio.to_thread(match_log.write_match_log, self.id, payload)
        except Exception:
            logger.exception("Failed to write match log for session %s", self.id)
