import unittest

from ...avge_abstracts.AVGEDeck import DeckType
from ...constants import User
from ..matchmaker import Matchmaker


class FakeTransport:
    def __init__(self):
        self.sent: list[dict] = []
        self.closed = False

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)

    async def close(self) -> None:
        self.closed = True


class MatchmakerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mm = Matchmaker()
        self._spawned_sessions = []

    async def asyncTearDown(self):
        for session in self._spawned_sessions:
            if session.task is not None and not session.task.done():
                session.task.cancel()
            session._cancel_all_timers()

    async def _join(self, account_id: str):
        session, user = await self.mm.join(account_id)
        self._spawned_sessions.append(session)
        return session, user

    async def test_first_join_creates_a_waiting_unstarted_session_as_player1(self):
        session, user = await self._join("acct-1")
        self.assertEqual(user, User.PLAYER_1)
        self.assertIn(session.id, self.mm.sessions)
        self.assertIsNone(session.task)
        self.assertEqual(session.seats[User.PLAYER_1].account_id, "acct-1")

    async def test_second_join_pairs_into_the_same_session_as_player2_and_prepares_it(self):
        session_a, user_a = await self._join("acct-1")
        session_b, user_b = await self._join("acct-2")
        self.assertIs(session_a, session_b)
        self.assertEqual(user_a, User.PLAYER_1)
        self.assertEqual(user_b, User.PLAYER_2)
        self.assertEqual(session_b.seats[User.PLAYER_2].account_id, "acct-2")
        # join() only prepares (deals hands) - it deliberately does NOT spawn the running task,
        # so the caller (ws_routes.py) can deliver game_start to both clients first via
        # session.begin_running() before any event traffic can be produced.
        self.assertIsNone(session_b.task)
        for user in (User.PLAYER_1, User.PLAYER_2):
            self.assertGreater(len(session_b.env.players[user].card_piles[DeckType.HAND]), 0)

        session_b.begin_running()
        self.assertIsNotNone(session_b.task)

    async def test_third_join_starts_a_brand_new_session(self):
        session_a, _ = await self._join("acct-1")
        await self._join("acct-2")  # pairs with session_a
        session_c, user_c = await self._join("acct-3")
        self.assertIsNot(session_c, session_a)
        self.assertEqual(user_c, User.PLAYER_1)

    async def test_find_active_game_resolves_after_join(self):
        session, user = await self._join("acct-1")
        await self._join("acct-2")
        result = self.mm.find_active_game("acct-1")
        self.assertEqual(result, (session, user))

    async def test_find_active_game_returns_none_for_unknown_account(self):
        self.assertIsNone(self.mm.find_active_game("nobody"))

    async def test_find_active_game_returns_none_after_session_finishes(self):
        session, user_a = await self._join("acct-1")
        _, user_b = await self._join("acct-2")
        t1, t2 = FakeTransport(), FakeTransport()
        session.attach(user_a, t1)
        session.attach(user_b, t2)

        await session.force_end(winner=user_b, reason="concede")

        self.assertNotIn(session.id, self.mm.sessions)
        self.assertIsNone(self.mm.find_active_game("acct-1"))
        self.assertIsNone(self.mm.find_active_game("acct-2"))

    async def test_session_that_dies_while_still_waiting_does_not_leak_the_empty_seat(self):
        # A session finishing while still _waiting (never paired) has one filled seat and one
        # with account_id still None - cleanup must skip that unfilled seat, not treat None as a
        # real account_id to look up.
        session, user_a = await self._join("acct-1")
        t1 = FakeTransport()
        session.attach(user_a, t1)
        await session.force_end(winner=user_a, reason="concede")
        self.assertIsNone(self.mm.find_active_game("acct-1"))


class ClaimReleaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mm = Matchmaker()

    async def test_first_claim_just_registers_no_kickout(self):
        t1 = FakeTransport()
        await self.mm.claim("acct-1", t1)
        self.assertFalse(t1.closed)
        self.assertEqual(t1.sent, [])

    async def test_second_claim_kicks_out_the_first(self):
        t1, t2 = FakeTransport(), FakeTransport()
        await self.mm.claim("acct-1", t1)
        await self.mm.claim("acct-1", t2)
        self.assertTrue(t1.closed)
        self.assertEqual(t1.sent, [{"type": "logged_out_elsewhere"}])
        self.assertFalse(t2.closed)

    async def test_claiming_with_the_same_websocket_again_is_a_no_op(self):
        t1 = FakeTransport()
        await self.mm.claim("acct-1", t1)
        await self.mm.claim("acct-1", t1)
        self.assertFalse(t1.closed)

    async def test_release_only_clears_if_still_the_current_connection(self):
        t1, t2 = FakeTransport(), FakeTransport()
        await self.mm.claim("acct-1", t1)
        await self.mm.claim("acct-1", t2)  # t1 is now stale/kicked
        self.mm.release("acct-1", t1)  # belated cleanup of the OLD connection
        self.assertIs(self.mm._active_connections["acct-1"], t2)  # must not have been cleared

        self.mm.release("acct-1", t2)
        self.assertNotIn("acct-1", self.mm._active_connections)


if __name__ == "__main__":
    unittest.main()
