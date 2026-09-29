import unittest

from ...avge_abstracts.AVGECard import AVGECard
from ...avge_abstracts.AVGEDeck import DeckType
from ...constants import CARDS_PER_DECK, User
from ...testing.helpers import Attacker, Dummy
from ..matchmaker import Matchmaker


def _deck(card_class: type[AVGECard] = Dummy) -> list[type[AVGECard]]:
    return [card_class] * CARDS_PER_DECK


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

    async def _join(self, account_id: str, deck: list[type[AVGECard]] | None = None):
        session, user = await self.mm.join(account_id, deck if deck is not None else _deck())
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

    async def test_leave_waiting_removes_the_queued_session_and_frees_the_account(self):
        session, _ = await self._join("acct-1")
        self.assertTrue(self.mm.leave_waiting("acct-1"))
        self.assertNotIn(session.id, self.mm.sessions)
        self.assertIsNone(self.mm.find_active_game("acct-1"))
        # The next joiner starts a fresh queue rather than pairing into the abandoned session.
        session_b, user_b = await self._join("acct-2")
        self.assertIsNot(session_b, session)
        self.assertEqual(user_b, User.PLAYER_1)

    async def test_leave_waiting_is_a_no_op_once_an_opponent_has_paired_in(self):
        session, _ = await self._join("acct-1")
        await self._join("acct-2")
        self.assertFalse(self.mm.leave_waiting("acct-1"))
        self.assertFalse(self.mm.leave_waiting("acct-2"))
        self.assertIn(session.id, self.mm.sessions)
        self.assertIsNotNone(self.mm.find_active_game("acct-1"))

    async def test_leave_waiting_with_nobody_queued_or_a_different_account_does_nothing(self):
        self.assertFalse(self.mm.leave_waiting("acct-1"))
        session, _ = await self._join("acct-1")
        self.assertFalse(self.mm.leave_waiting("acct-2"))
        self.assertIn(session.id, self.mm.sessions)

    async def test_each_players_own_deck_survives_pairing_with_no_crossover(self):
        # Regression guard for a seat/deck mixup: pair two players with deliberately different
        # decks and confirm each one's active/hand/deck ends up built only from their OWN classes,
        # never the opponent's.
        session_a, user_a = await self._join("acct-1", deck=_deck(Dummy))
        session_b, user_b = await self._join("acct-2", deck=_deck(Attacker))
        self.assertIs(session_a, session_b)
        session = session_a

        def _all_cards(user):
            player = session.env.players[user]
            cards = list(player.card_piles[DeckType.HAND].cards_holding)
            cards += player.card_piles[DeckType.ACTIVE_CARD].cards_holding
            cards += player.card_piles[DeckType.DECK].cards_holding
            return cards

        self.assertTrue(all(isinstance(c, Dummy) for c in _all_cards(user_a)))
        self.assertTrue(all(isinstance(c, Attacker) for c in _all_cards(user_b)))

    async def test_a_duplicate_join_for_the_same_account_never_creates_a_stray_session(self):
        # Regression test for the reorder in join(): the account gets registered in
        # _active_game_by_account BEFORE prepare() is awaited now, not after - so a second join()
        # call for the same account (even one that could in principle land mid-prepare()) always
        # finds the same session via find_active_game() rather than racing to create a third one.
        session_a, user_a = await self._join("acct-1")
        session_b, user_b = await self._join("acct-2")
        # A duplicate join for acct-1 (already paired) must return the existing session/seat.
        session_c, user_c = await self._join("acct-1")
        self.assertIs(session_c, session_a)
        self.assertEqual(user_c, user_a)
        self.assertEqual(len(self.mm.sessions), 1)


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
