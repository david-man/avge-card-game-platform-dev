from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from ...avge_abstracts.AVGECard import AVGECard
from ...constants import CARDS_PER_DECK, User
from ...testing.helpers import Dummy
from ..app import create_app
from ..matchmaker import Matchmaker, normalize_private_code
from ._ws_test_utils import QueuedWebSocket, login, login_with_deck


def _deck() -> list[type[AVGECard]]:
    return [Dummy] * CARDS_PER_DECK


class PrivateMatchmakerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mm = Matchmaker()
        self.sessions = []

    async def asyncTearDown(self):
        for session in self.sessions:
            if session.task is not None and not session.task.done():
                session.task.cancel()
            session._cancel_all_timers()

    def _create(self, account_id: str):
        session, user = self.mm.create_private(account_id, _deck())
        self.sessions.append(session)
        return session, user

    async def test_private_waiting_room_is_separate_from_public_queue(self):
        private, user = self._create("host")
        self.assertEqual(user, User.PLAYER_1)
        self.assertIsNone(self.mm._waiting)
        public, _ = await self.mm.join("public", _deck())
        self.sessions.append(public)
        self.assertIsNot(private, public)
        guest_session, guest_user = await self.mm.join_private(
            "guest", _deck(), private.invite_code.lower().replace("-", " "),
        )
        self.assertIs(guest_session, private)
        self.assertEqual(guest_user, User.PLAYER_2)
        self.assertEqual(private.stage, "setup")
        self.assertIs(self.mm._waiting, public)
        with self.assertRaisesRegex(ValueError, "no longer available"):
            await self.mm.join_private("late", _deck(), private.invite_code)

    async def test_bad_deck_does_not_consume_the_code(self):
        private, _ = self._create("host")
        with self.assertRaises(ValueError):
            await self.mm.join_private("guest", [], private.invite_code)
        self.assertIn(normalize_private_code(private.invite_code), self.mm._private_waiting)
        self.assertIsNone(self.mm.find_active_game("guest"))

    async def test_host_cancellation_and_disconnect_invalidate_the_code(self):
        private, _ = self._create("host")
        code = private.invite_code
        self.assertTrue(self.mm.leave_waiting("host"))
        self.assertIsNone(self.mm.find_active_game("host"))
        with self.assertRaises(ValueError):
            await self.mm.join_private("guest", _deck(), code)

        private, _ = self._create("host")
        socket = object()
        private.seats[User.PLAYER_1].websocket = socket
        self.mm.cancel_private_on_disconnect("host", socket)
        self.assertIsNone(self.mm.find_active_game("host"))
        self.assertNotIn(normalize_private_code(private.invite_code), self.mm._private_waiting)

    async def test_stale_host_socket_does_not_cancel_a_reconnected_room(self):
        private, _ = self._create("host")
        stale = object()
        current = object()
        private.seats[User.PLAYER_1].websocket = current
        self.mm.cancel_private_on_disconnect("host", stale)
        self.assertIsNotNone(self.mm.find_active_game("host"))

    async def test_code_collision_is_retried(self):
        with patch(
            "card_game_v2.server.matchmaker.secrets.choice",
            side_effect=list("A" * 20 + "B" * 10),
        ):
            first, _ = self._create("first")
            self.mm.leave_waiting("first")
            second, _ = self._create("second")
        self.assertEqual(first.invite_code, "AAAAA-AAAAA")
        self.assertEqual(second.invite_code, "BBBBB-BBBBB")

    async def test_simultaneous_guests_cannot_claim_the_same_code(self):
        private, _ = self._create("host")
        results = await asyncio.gather(
            self.mm.join_private("guest-a", _deck(), private.invite_code),
            self.mm.join_private("guest-b", _deck(), private.invite_code),
            return_exceptions=True,
        )
        self.assertEqual(sum(isinstance(result, tuple) for result in results), 1)
        self.assertEqual(sum(isinstance(result, ValueError) for result in results), 1)
        self.assertEqual(private.stage, "setup")

    def test_code_format_rejects_ambiguous_characters(self):
        self.assertEqual(normalize_private_code("abcde-fghjk"), "ABCDEFGHJK")
        with self.assertRaises(ValueError):
            normalize_private_code("OOOOO-OOOOO")


class PrivateWebSocketTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.app = create_app(data_dir=Path(self._tmpdir.name))
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.addCleanup(lambda: self.client.__exit__(None, None, None))

    def test_create_join_and_reused_code(self):
        with self.client.websocket_connect("/ws") as raw_host:
            host = QueuedWebSocket(raw_host)
            login_with_deck(self.client, host, "host")
            host.send_json({"type": "create_private"})
            joined_host = host.receive_json()
            self.assertEqual(joined_host["match_mode"], "private")
            code = joined_host["invite_code"]
            self.assertEqual(len(code), 11)
            self.assertEqual(host.receive_json()["type"], "waiting_for_opponent")

            with self.client.websocket_connect("/ws") as raw_guest:
                guest = QueuedWebSocket(raw_guest)
                login_with_deck(self.client, guest, "guest")
                guest.send_json({"type": "join_private", "code": code.lower()})
                joined_guest = guest.receive_json()
                self.assertEqual(joined_guest["type"], "joined")
                self.assertEqual(joined_guest["match_mode"], "private")
                self.assertIsNone(joined_guest["invite_code"])
                self.assertEqual(joined_guest["game_id"], joined_host["game_id"])
                self.assertEqual(guest.receive_json()["type"], "setup_start")
                self.assertEqual(host.receive_json()["type"], "setup_start")

                with self.client.websocket_connect("/ws") as raw_late:
                    late = QueuedWebSocket(raw_late)
                    login_with_deck(self.client, late, "late")
                    late.send_json({"type": "join_private", "code": code})
                    error = late.receive_json()
                    self.assertEqual(error["code"], "private_join_failed")
                    self.assertIn("no longer available", error["message"])

    def test_no_deck_cannot_create_or_join(self):
        with self.client.websocket_connect("/ws") as raw_no_deck:
            no_deck = QueuedWebSocket(raw_no_deck)
            login(no_deck, "no-deck-host")
            no_deck.send_json({"type": "create_private"})
            self.assertEqual(no_deck.receive_json()["code"], "no_deck_selected")
            self.assertIsNone(self.app.state.matchmaker.find_active_game("no-deck-host"))

        with self.client.websocket_connect("/ws") as raw_host:
            host = QueuedWebSocket(raw_host)
            login_with_deck(self.client, host, "host")
            host.send_json({"type": "create_private"})
            code = host.receive_json()["invite_code"]
            host.receive_json()
            with self.client.websocket_connect("/ws") as raw_guest:
                guest = QueuedWebSocket(raw_guest)
                login(guest, "guest")
                guest.send_json({"type": "join_private", "code": code})
                self.assertEqual(guest.receive_json()["code"], "no_deck_selected")
                self.assertIn(normalize_private_code(code), self.app.state.matchmaker._private_waiting)

    def test_prepare_failure_lets_host_create_again_on_same_socket(self):
        with self.client.websocket_connect("/ws") as raw_host:
            host = QueuedWebSocket(raw_host)
            login_with_deck(self.client, host, "host")
            host.send_json({"type": "create_private"})
            first_code = host.receive_json()["invite_code"]
            host.receive_json()
            with self.client.websocket_connect("/ws") as raw_guest:
                guest = QueuedWebSocket(raw_guest)
                login_with_deck(self.client, guest, "guest")
                with patch(
                    "card_game_v2.server.session.GameSession.prepare",
                    new_callable=AsyncMock,
                    side_effect=RuntimeError("forced preparation failure"),
                ):
                    guest.send_json({"type": "join_private", "code": first_code})
                    self.assertEqual(guest.receive_json()["code"], "game_start_failed")
                self.assertEqual(host.receive_json()["type"], "left")
                self.assertEqual(host.receive_json()["code"], "private_start_failed")
                host.send_json({"type": "create_private"})
                replacement = host.receive_json()
                self.assertEqual(replacement["type"], "joined")
                self.assertNotEqual(replacement["invite_code"], first_code)
                self.assertEqual(host.receive_json()["type"], "waiting_for_opponent")

    def test_host_disconnect_closes_unjoined_room(self):
        with self.client.websocket_connect("/ws") as raw_host:
            host = QueuedWebSocket(raw_host)
            login_with_deck(self.client, host, "host")
            host.send_json({"type": "create_private"})
            code = host.receive_json()["invite_code"]
            host.receive_json()
        self.assertNotIn(normalize_private_code(code), self.app.state.matchmaker._private_waiting)

    def test_reconnect_after_pairing_restores_setup(self):
        with self.client.websocket_connect("/ws") as raw_host:
            host = QueuedWebSocket(raw_host)
            login_with_deck(self.client, host, "host")
            host.send_json({"type": "create_private"})
            code = host.receive_json()["invite_code"]
            host.receive_json()
            with self.client.websocket_connect("/ws") as raw_guest:
                guest = QueuedWebSocket(raw_guest)
                login_with_deck(self.client, guest, "guest")
                guest.send_json({"type": "join_private", "code": code})
                guest.receive_json()
                guest.receive_json()
                host.receive_json()
                with self.client.websocket_connect("/ws") as raw_host_again:
                    host_again = QueuedWebSocket(raw_host_again)
                    login(host_again, "host")
                    self.assertEqual(host.receive_json()["type"], "logged_out_elsewhere")
                    joined = host_again.receive_json()
                    self.assertEqual(joined["match_mode"], "private")
                    self.assertEqual(host_again.receive_json()["type"], "setup_start")


if __name__ == "__main__":
    unittest.main()
