import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from ...avge_abstracts.AVGEDeck import DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes, User, WinReasons
from ...core.EventCatalog import PlayCharacterCard
from ...engine.event import Packet
from ...testing.helpers import Attacker, Dummy
from .. import config as server_config
from ..decks import CARDS_PER_DECK
from ..session import GameSession


class FakeTransport:
    def __init__(self):
        self.sent: list[dict] = []
        self.closed = False

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)

    async def close(self) -> None:
        self.closed = True


class SessionTestBase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.finished_ids: list[str] = []
        self.session = GameSession("game-1", self.finished_ids.append)
        self.t1 = FakeTransport()
        self.t2 = FakeTransport()

    async def asyncTearDown(self):
        # Make sure no test leaves a real long-running task/timer behind.
        if self.session.task is not None and not self.session.task.done():
            self.session.task.cancel()
        self.session._cancel_all_timers()


class StartTests(SessionTestBase):
    async def test_start_deals_hands_and_spawns_a_running_task(self):
        await self.session.start()
        try:
            for user in (User.PLAYER_1, User.PLAYER_2):
                player = self.session.env.players[user]
                self.assertEqual(len(player.card_piles[DeckType.ACTIVE_CARD]), 1)
                self.assertGreater(len(player.card_piles[DeckType.HAND]), 0)
            self.assertIsNotNone(self.session.task)
            assert self.session.task is not None
            self.assertFalse(self.session.task.done())
        finally:
            self.session.task.cancel()  # type: ignore[union-attr]
            try:
                await self.session.task
            except asyncio.CancelledError:
                pass


class ConfigureDecksTests(SessionTestBase):
    async def test_a_bare_session_already_has_a_fully_built_placeholder_env(self):
        # The invariant configure_decks()'s whole design rests on: GameSession.__init__ must
        # never leave self.env as None, since force_end()/_abandon() (and dozens of tests) act on
        # a session without ever calling prepare()/configure_decks() first.
        for user in User:
            self.assertEqual(
                len(self.session.env.players[user].card_piles[DeckType.DECK]), CARDS_PER_DECK,
            )

    async def test_configure_decks_replaces_env_and_repoints_io(self):
        placeholder_env = self.session.env
        self.session.seats[User.PLAYER_1].deck = [Dummy] * 20
        self.session.seats[User.PLAYER_2].deck = [Attacker] * 20

        self.session.configure_decks()

        self.assertIsNot(self.session.env, placeholder_env)
        self.assertIs(self.session.io.env, self.session.env)
        p1_deck = self.session.env.players[User.PLAYER_1].card_piles[DeckType.DECK].cards_holding
        p2_deck = self.session.env.players[User.PLAYER_2].card_piles[DeckType.DECK].cards_holding
        self.assertTrue(all(isinstance(c, Dummy) for c in p1_deck))
        self.assertTrue(all(isinstance(c, Attacker) for c in p2_deck))

    async def test_prepare_after_configure_decks_deals_from_the_custom_decks_not_the_preset_pool(self):
        self.session.seats[User.PLAYER_1].deck = [Dummy] * 20
        self.session.seats[User.PLAYER_2].deck = [Attacker] * 20
        self.session.configure_decks()

        await self.session.prepare()

        active_p1 = self.session.env.players[User.PLAYER_1].card_piles[DeckType.ACTIVE_CARD].cards_holding
        active_p2 = self.session.env.players[User.PLAYER_2].card_piles[DeckType.ACTIVE_CARD].cards_holding
        self.assertEqual(len(active_p1), 1)
        self.assertEqual(len(active_p2), 1)
        self.assertIsInstance(active_p1[0], Dummy)
        self.assertIsInstance(active_p2[0], Attacker)

    async def test_configure_decks_asserts_if_a_seat_has_no_deck_set(self):
        # Only PLAYER_1's deck is set - PLAYER_2's stays None, matching the real ordering bug this
        # guards against (calling configure_decks() before Matchmaker.join() has resolved both
        # accounts' decks).
        self.session.seats[User.PLAYER_1].deck = [Dummy] * 20
        with self.assertRaises(AssertionError):
            self.session.configure_decks()

    async def test_configure_decks_refuses_once_the_session_is_running(self):
        for seat in self.session.seats.values():
            seat.deck = [Dummy] * 20
        await self.session.start()
        try:
            with self.assertRaises(AssertionError):
                self.session.configure_decks()
        finally:
            self.session.task.cancel()  # type: ignore[union-attr]
            try:
                await self.session.task
            except asyncio.CancelledError:
                pass


class ConnectionStateTests(SessionTestBase):
    async def test_attach_marks_seat_connected(self):
        result = self.session.attach(User.PLAYER_1, self.t1)
        self.assertTrue(result)
        seat = self.session.seats[User.PLAYER_1]
        self.assertTrue(seat.connected)
        self.assertIs(seat.websocket, self.t1)

    async def test_attach_after_force_end_is_refused(self):
        self.session.attach(User.PLAYER_1, self.t1)
        await self.session.force_end(winner=User.PLAYER_1, reason="concede")

        result = self.session.attach(User.PLAYER_2, self.t2)

        self.assertFalse(result)
        seat = self.session.seats[User.PLAYER_2]
        self.assertFalse(seat.connected)
        self.assertIsNone(seat.websocket)

    async def test_detach_with_opponent_still_connected_starts_a_grace_timer(self):
        self.session.attach(User.PLAYER_1, self.t1)
        self.session.attach(User.PLAYER_2, self.t2)
        self.session.detach(User.PLAYER_1, self.t1)
        seat = self.session.seats[User.PLAYER_1]
        self.assertFalse(seat.connected)
        self.assertIsNotNone(seat.disconnect_task)

    async def test_detach_notifies_the_still_connected_opponent(self):
        server_config.RECONNECT_GRACE_SECONDS = 30.0
        self.session.attach(User.PLAYER_1, self.t1)
        self.session.attach(User.PLAYER_2, self.t2)
        self.session.detach(User.PLAYER_1, self.t1)
        await asyncio.sleep(0)  # let the fire-and-forget notify task run
        self.assertEqual(self.t2.sent, [{"type": "opponent_disconnected", "grace_seconds": 30.0}])
        self.assertEqual(self.t1.sent, [])

    async def test_detach_with_both_disconnected_sends_no_notification(self):
        self.session.attach(User.PLAYER_1, self.t1)
        self.session.attach(User.PLAYER_2, self.t2)
        self.session.detach(User.PLAYER_1, self.t1)
        self.session.detach(User.PLAYER_2, self.t2)
        await asyncio.sleep(0)
        self.assertEqual(self.t1.sent, [])
        self.assertEqual(self.t2.sent, [])

    async def test_lone_waiting_occupant_detaching_does_not_abandon_the_session(self):
        # Regression guard: a session with only one seat ever attached (the matchmaker's waiting
        # slot, before a second player has paired in - see Matchmaker.join()) must NOT be treated
        # as "both players abandoned a match" when that lone occupant disconnects. Otherwise a
        # vanished lone waiter would kill the session outright, and a genuinely new second player
        # could never pair into it and get the usual reconnect-grace treatment for the first
        # player (see test_begin_running_arms_a_grace_timer_for_a_seat_already_disconnected_before_start).
        self.session.attach(User.PLAYER_1, self.t1)
        self.session.detach(User.PLAYER_1, self.t1)
        await asyncio.sleep(0)
        self.assertFalse(self.session.finished)
        self.assertIsNone(self.session.seats[User.PLAYER_1].disconnect_task)

    async def test_reconnect_within_grace_cancels_the_timer(self):
        server_config.RECONNECT_GRACE_SECONDS = 5.0
        self.session.attach(User.PLAYER_1, self.t1)
        self.session.attach(User.PLAYER_2, self.t2)
        self.session.detach(User.PLAYER_1, self.t1)
        self.session.attach(User.PLAYER_1, self.t1)
        seat = self.session.seats[User.PLAYER_1]
        self.assertTrue(seat.connected)
        self.assertIsNone(seat.disconnect_task)
        self.assertFalse(self.session.finished)

    async def test_a_stale_connections_belated_detach_does_not_disconnect_a_newer_one(self):
        # E.g. a connection superseded by precedence (Matchmaker.claim()) whose own
        # WebSocketDisconnect handling runs AFTER a brand new connection has already reattached -
        # the old one's detach() call must be a no-op, not wipe out the new attachment.
        old_transport = FakeTransport()
        new_transport = FakeTransport()
        self.session.attach(User.PLAYER_1, old_transport)
        self.session.attach(User.PLAYER_1, new_transport)  # a newer connection takes over the seat

        self.session.detach(User.PLAYER_1, old_transport)  # belated cleanup of the stale one

        seat = self.session.seats[User.PLAYER_1]
        self.assertTrue(seat.connected)
        self.assertIs(seat.websocket, new_transport)

    async def test_disconnect_timeout_forces_end_with_opponent_as_winner(self):
        server_config.RECONNECT_GRACE_SECONDS = 0.01
        try:
            self.session.attach(User.PLAYER_1, self.t1)
            self.session.attach(User.PLAYER_2, self.t2)
            self.session.detach(User.PLAYER_1, self.t1)
            await asyncio.sleep(0.05)
            self.assertTrue(self.session.finished)
            self.assertEqual(self.session.env.winner, User.PLAYER_2)
            self.assertEqual(self.session.env.win_reason, WinReasons.DISCONNECT_TIMEOUT)
            self.assertEqual(self.finished_ids, ["game-1"])
            # t2 gets both the immediate opponent_disconnected notice and the eventual game_over.
            self.assertEqual(self.t2.sent[0], {"type": "opponent_disconnected", "grace_seconds": 0.01})
            self.assertEqual(self.t2.sent[-1], {"type": "game_over", "winner": User.PLAYER_2.name, "reason": "disconnect_timeout"})
        finally:
            server_config.RECONNECT_GRACE_SECONDS = 30.0

    async def test_both_disconnected_abandons_with_no_winner(self):
        self.session.attach(User.PLAYER_1, self.t1)
        self.session.attach(User.PLAYER_2, self.t2)
        self.session.detach(User.PLAYER_1, self.t1)
        self.session.detach(User.PLAYER_2, self.t2)
        await asyncio.sleep(0.05)  # let the fire-and-forget abandon task run to completion
        self.assertTrue(self.session.finished)
        self.assertIsNone(self.session.env.winner)
        self.assertEqual(self.finished_ids, ["game-1"])

    async def test_sequential_disconnects_abandons_immediately_not_after_grace(self):
        # Regression test: when both seats disconnect sequentially (the realistic case, unlike the
        # simultaneous double-detach in the test above), the first seat's own _disconnect_grace
        # timer - started earlier - used to always win the race and force a win for the SECOND
        # disconnector once it elapsed, even though they were equally absent by then. Both-
        # disconnected abandonment is now triggered immediately from detach() the moment the second
        # player disconnects (which also cancels the first seat's still-pending _disconnect_grace
        # task via _cancel_all_timers()), so this must resolve as an abandonment well before
        # RECONNECT_GRACE_SECONDS could ever elapse.
        server_config.RECONNECT_GRACE_SECONDS = 5.0
        try:
            self.session.attach(User.PLAYER_1, self.t1)
            self.session.attach(User.PLAYER_2, self.t2)
            self.session.detach(User.PLAYER_1, self.t1)
            await asyncio.sleep(0.005)  # a realistic gap, not a simultaneous double-detach
            self.session.detach(User.PLAYER_2, self.t2)

            await asyncio.sleep(0.05)  # let the fire-and-forget abandon task run to completion
            self.assertTrue(self.session.finished)
            self.assertIsNone(self.session.env.winner)
        finally:
            server_config.RECONNECT_GRACE_SECONDS = 30.0

    async def test_begin_running_arms_a_grace_timer_for_a_seat_already_disconnected_before_start(self):
        # Reproduces the "ghost opponent" bug: a seat that vanished before the game ever started
        # running (e.g. Matchmaker.join() pairing a new player into a still-waiting session whose
        # original occupant already disconnected) must still get an active grace timer once the
        # game actually begins - otherwise detach() can never (re)arm one for it later, since
        # detach() no-ops for a seat that's already disconnected.
        server_config.RECONNECT_GRACE_SECONDS = 0.01
        try:
            self.session.attach(User.PLAYER_1, self.t1)
            self.session.detach(User.PLAYER_1, self.t1)  # vanishes while waiting alone
            await self.session.prepare()
            self.session.attach(User.PLAYER_2, self.t2)  # a new player pairs in and the game starts
            self.assertIsNone(self.session.seats[User.PLAYER_1].disconnect_task)

            self.session.begin_running()
            self.assertIsNotNone(self.session.seats[User.PLAYER_1].disconnect_task)
            await asyncio.sleep(0)  # let the fire-and-forget notify task run
            self.assertEqual(self.t2.sent, [{"type": "opponent_disconnected", "grace_seconds": 0.01}])

            await asyncio.sleep(0.05)
            self.assertTrue(self.session.finished)
            self.assertEqual(self.session.env.winner, User.PLAYER_2)
            self.assertEqual(self.session.env.win_reason, WinReasons.DISCONNECT_TIMEOUT)
        finally:
            server_config.RECONNECT_GRACE_SECONDS = 30.0

    async def test_begin_running_abandons_immediately_if_both_seats_already_disconnected(self):
        # Narrow, defensive-only scenario: both seats already show as not connected by the time
        # begin_running() runs, without having gone through detach()'s own immediate-abandon path
        # (which would already have handled it) - e.g. a transport failure flips `connected`
        # without the usual detach() call. There's no opponent left to notify or wait out a grace
        # period for, so this must abandon immediately rather than leaking the session with no
        # cleanup path.
        self.session.attach(User.PLAYER_1, self.t1)
        self.session.attach(User.PLAYER_2, self.t2)
        await self.session.prepare()
        self.session.seats[User.PLAYER_1].connected = False
        self.session.seats[User.PLAYER_2].connected = False

        self.session.begin_running()
        await asyncio.sleep(0.05)  # let the fire-and-forget abandon task run to completion
        self.assertTrue(self.session.finished)
        self.assertIsNone(self.session.env.winner)

    async def test_reconnecting_before_the_abandon_task_runs_prevents_abandonment(self):
        # detach() schedules _abandon() via asyncio.create_task() rather than running it inline,
        # leaving a real (if brief) scheduling gap before it actually executes. _abandon() itself
        # re-checks connection state when it runs (not just self.finished) specifically to cover a
        # reconnect landing in that gap - this exercises exactly that path.
        self.session.attach(User.PLAYER_1, self.t1)
        self.session.attach(User.PLAYER_2, self.t2)
        self.session.detach(User.PLAYER_1, self.t1)
        self.session.detach(User.PLAYER_2, self.t2)  # schedules an _abandon() task
        self.session.attach(User.PLAYER_1, self.t1)  # reconnects before that task gets to run
        await asyncio.sleep(0)  # let the scheduled task actually run now
        self.assertFalse(self.session.finished)


class ForceEndTests(SessionTestBase):
    async def test_concede_forces_end_and_notifies_both_connected_seats(self):
        self.session.attach(User.PLAYER_1, self.t1)
        self.session.attach(User.PLAYER_2, self.t2)
        await self.session.force_end(winner=User.PLAYER_2, reason="concede")
        self.assertTrue(self.session.finished)
        self.assertEqual(self.session.env.winner, User.PLAYER_2)
        self.assertEqual(self.session.env.win_reason, WinReasons.CONCEDE)
        expected = {"type": "game_over", "winner": User.PLAYER_2.name, "reason": "concede"}
        self.assertEqual(self.t1.sent, [expected])
        self.assertEqual(self.t2.sent, [expected])
        self.assertEqual(self.finished_ids, ["game-1"])

    async def test_force_end_only_notifies_connected_seats(self):
        self.session.attach(User.PLAYER_2, self.t2)
        await self.session.force_end(winner=User.PLAYER_2, reason="concede")
        self.assertEqual(self.t1.sent, [])
        self.assertEqual(len(self.t2.sent), 1)

    async def test_force_end_is_idempotent(self):
        self.session.attach(User.PLAYER_1, self.t1)
        self.session.attach(User.PLAYER_2, self.t2)
        await self.session.force_end(winner=User.PLAYER_2, reason="concede")
        await self.session.force_end(winner=User.PLAYER_1, reason="concede")  # no-op, already finished
        self.assertEqual(self.session.env.winner, User.PLAYER_2)  # unchanged
        self.assertEqual(len(self.finished_ids), 1)

    async def test_force_end_cancels_the_running_task(self):
        await self.session.start()
        await self.session.force_end(winner=User.PLAYER_1, reason="concede")
        assert self.session.task is not None
        self.assertTrue(self.session.task.done())


class PausingTransport(FakeTransport):
    '''A transport whose send_json() parks on a test-controlled gate before actually sending -
    used to deterministically land inside force_end()'s window between `self.finished = True`
    and _finish() actually deregistering the session, reproducing the reconnect race described
    in session.py's attach() docstring instead of just testing the obvious already-finished
    case.'''
    def __init__(self, gate: asyncio.Event):
        super().__init__()
        self.gate = gate

    async def send_json(self, data: dict) -> None:
        await self.gate.wait()
        await super().send_json(data)


class ReconnectRaceTests(SessionTestBase):
    async def test_attach_is_refused_while_force_end_is_still_mid_teardown(self):
        gate = asyncio.Event()
        paused_t1 = PausingTransport(gate)
        self.session.attach(User.PLAYER_1, paused_t1)
        self.session.attach(User.PLAYER_2, self.t2)

        force_end_task = asyncio.create_task(
            self.session.force_end(winner=User.PLAYER_2, reason="concede"),
        )
        # Let force_end run up to `self.finished = True` and park on PLAYER_1's paused send -
        # before it has ever reached _finish()/_on_finished().
        await asyncio.sleep(0)
        self.assertTrue(self.session.finished)
        self.assertFalse(force_end_task.done())
        self.assertEqual(self.finished_ids, [])

        # A reconnect landing exactly in this gap must not rebind the seat.
        new_transport = FakeTransport()
        result = self.session.attach(User.PLAYER_1, new_transport)
        self.assertFalse(result)
        self.assertIs(self.session.seats[User.PLAYER_1].websocket, paused_t1)

        gate.set()
        await force_end_task
        self.assertEqual(self.finished_ids, ["game-1"])


class NaturalCompletionTests(SessionTestBase):
    async def test_run_wrapper_calls_on_finished_when_env_run_returns_naturally(self):
        # env.run() returns immediately when the packet queue is already empty (Engine.flush()'s
        # own while-loop condition) - a minimal way to exercise the "game ended naturally, not
        # via force_end/_abandon" path without driving a full KO sequence.
        self.session.task = asyncio.create_task(self.session._run_wrapper())
        await asyncio.wait_for(self.session.task, timeout=1.0)
        self.assertTrue(self.session.finished)
        self.assertEqual(self.finished_ids, ["game-1"])


class FailurePathTests(SessionTestBase):
    '''A bug anywhere in the engine's own execution must not leave the session hanging forever -
    see GameSession._fail(). Without this, both players would just be stuck with no game_over.'''

    async def test_unhandled_exception_kicks_both_players_and_cleans_up(self):
        self.session.attach(User.PLAYER_1, self.t1)
        self.session.attach(User.PLAYER_2, self.t2)

        async def raising_run():
            raise RuntimeError("boom")

        self.session.env.run = raising_run  # type: ignore[method-assign]

        with tempfile.TemporaryDirectory() as tmp:
            server_config.MATCH_LOG_DIR = Path(tmp)
            try:
                with self.assertLogs("card_game_v2.server.session", level="ERROR"):
                    self.session.task = asyncio.create_task(self.session._run_wrapper())
                    await asyncio.wait_for(self.session.task, timeout=1.0)

                self.assertTrue(self.session.finished)
                self.assertEqual(self.finished_ids, ["game-1"])
                expected = {"type": "game_over", "winner": None, "reason": "server_error"}
                self.assertEqual(self.t1.sent, [expected])
                self.assertEqual(self.t2.sent, [expected])

                match_log_path = Path(tmp) / "game-1.json"
                self.assertTrue(match_log_path.exists())
                payload = json.loads(match_log_path.read_text())
                fatal_entries = [e for e in payload["lifecycle"] if e["kind"] == "fatal_error"]
                self.assertEqual(len(fatal_entries), 1)
                self.assertIn("boom", fatal_entries[0]["detail"])
            finally:
                server_config.MATCH_LOG_DIR = server_config.LOG_DIR / "matches"


class LifecycleLogTests(SessionTestBase):
    def _kinds(self) -> list[str]:
        return [e["kind"] for e in self.session._lifecycle]

    async def test_attach_logs_connect_and_reconnect(self):
        self.session.attach(User.PLAYER_1, self.t1)
        self.assertEqual(self._kinds(), ["attach"])
        self.assertFalse(self.session._lifecycle[0]["reconnect"])

        self.session.attach(User.PLAYER_2, self.t2)
        self.session.detach(User.PLAYER_2, self.t2)
        self.session.attach(User.PLAYER_2, self.t2)
        self.assertEqual(self._kinds(), ["attach", "attach", "detach", "attach"])
        self.assertTrue(self.session._lifecycle[-1]["reconnect"])

    async def test_force_end_and_abandon_are_logged(self):
        self.session.attach(User.PLAYER_1, self.t1)
        self.session.attach(User.PLAYER_2, self.t2)
        await self.session.force_end(winner=User.PLAYER_1, reason="concede")
        entries = [e for e in self.session._lifecycle if e["kind"] == "forced_end"]
        self.assertEqual(entries, [{"ts": entries[0]["ts"], "kind": "forced_end", "winner": "PLAYER_1", "reason": "concede"}])

    async def test_abandon_is_logged(self):
        self.session.attach(User.PLAYER_1, self.t1)
        self.session.attach(User.PLAYER_2, self.t2)
        self.session.detach(User.PLAYER_1, self.t1)
        self.session.detach(User.PLAYER_2, self.t2)
        await asyncio.sleep(0.05)  # let the fire-and-forget abandon task run to completion
        self.assertIn("abandoned", self._kinds())


class PacketRejectionLoggingTests(SessionTestBase):
    '''Exercises GameSession._log_packet_rejection() - composed into env.engine.on_packet_failed
    via game_setup.perform_initial_setup()'s extra_on_packet_failed parameter - by calling the
    wired hook with a bare Packet - rather than trying to trigger a
    real REGULATE_FAIL through actual gameplay against a real preset deck with no client attached
    to answer any IO, which is both fragile (deck-dependent) and can hang if the specific card's
    act() needs any IO before its validity check would even run. The already-existing
    testing/test_engine_hooks.py separately proves on_packet_failed itself fires correctly on a
    real REGULATE_FAIL at the engine level (with a controlled TestIO-driven scenario); this test
    only needs to prove the session-level wrapper records the rejection.'''

    async def test_regulate_fail_is_captured_in_lifecycle_log(self):
        await self.session.prepare()
        env = self.session.env
        env.turn = User.PLAYER_1
        active = env.players[User.PLAYER_1].card_piles[DeckType.ACTIVE_CARD].cards_holding[0]

        _id = AVGEEngineID(None, ActionTypes.ENV, None)
        failing_event = PlayCharacterCard(_id, active, ActionTypes.ATK_1, 1, env)
        pkt = Packet(_id, [])
        pkt.current_event = failing_event

        assert env.engine.on_packet_failed is not None
        await env.engine.on_packet_failed(pkt)

        rejected = [e for e in self.session._lifecycle if e["kind"] == "packet_rejected"]
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["for_user"], "PLAYER_1")
        self.assertEqual(rejected[0]["failed_on"], ["PlayCharacterCard"])
        self.assertEqual(rejected[0]["committed_before_failure"], [])


if __name__ == "__main__":
    unittest.main()
