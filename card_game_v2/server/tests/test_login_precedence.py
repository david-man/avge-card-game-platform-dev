import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from ..app import create_app
from ._ws_test_utils import QueuedWebSocket, drain_for_type, login, login_with_deck


class LoginPrecedenceIntegrationTests(unittest.TestCase):
    '''Real TestClient sockets - proves account-based session precedence and cross-tab
    reconnection end-to-end (not just Matchmaker.claim()/release()/find_active_game() in
    isolation, already covered by test_matchmaker.py).'''

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        # Shared portal across every websocket_connect() in this test - see
        # test_full_game_two_fake_clients.py's setUp for why a bare TestClient(app) is unsafe.
        self.client = TestClient(create_app(data_dir=Path(self._tmpdir.name)))
        self.client.__enter__()
        self.addCleanup(lambda: self.client.__exit__(None, None, None))

    def test_second_login_with_same_username_kicks_out_the_first(self):
        with self.client.websocket_connect("/ws") as raw1:
            ws1 = QueuedWebSocket(raw1)
            login(ws1, "alice")

            with self.client.websocket_connect("/ws") as raw2:
                ws2 = QueuedWebSocket(raw2)
                logged_in_2 = login(ws2, "alice")

                kicked = drain_for_type(ws1, "logged_out_elsewhere")
                self.assertEqual(kicked, {"type": "logged_out_elsewhere"})
                # Both logins resolve to the same persistent account.
                self.assertTrue(logged_in_2["account_id"])

    def test_reconnecting_via_auth_token_is_routed_straight_back_into_the_live_game(self):
        with self.client.websocket_connect("/ws") as raw1:
            ws1 = QueuedWebSocket(raw1)
            login_with_deck(self.client, ws1, "alice")
            ws1.send_json({"type": "join"})
            ws1.receive_json()  # joined
            ws1.receive_json()  # waiting_for_opponent

            with self.client.websocket_connect("/ws") as raw2:
                ws2 = QueuedWebSocket(raw2)
                login_with_deck(self.client, ws2, "bob")
                ws2.send_json({"type": "join"})
                ws2.receive_json()  # joined
                ws2.receive_json()  # game_start
                ws1.receive_json()  # game_start

                # A brand new connection (a different tab/context) logs in as "alice" again -
                # no client-sent join/rejoin message is needed; the server resends a JoinedMessage
                # (so the client learns its own seat again) followed by game_start, and the
                # opponent (bob) should see the disconnect notice replaced by a reconnect one.
                with self.client.websocket_connect("/ws") as raw1b:
                    ws1b = QueuedWebSocket(raw1b)
                    login(ws1b, "alice")

                    # The original ws1 gets kicked (precedence) - its own disconnect flows into
                    # the normal WebSocketDisconnect -> session.detach() path.
                    drain_for_type(ws1, "logged_out_elsewhere")

                    reconnected_snapshot = drain_for_type(ws1b, "game_start")
                    self.assertIn("players", reconnected_snapshot["snapshot"])

                    # bob should see the opponent_disconnected notice clear via
                    # opponent_reconnected, without ever needing to do anything itself.
                    opponent_reconnected = drain_for_type(ws2, "opponent_reconnected")
                    self.assertIn("players", opponent_reconnected["snapshot"])

    def test_reconnecting_while_still_waiting_for_an_opponent_gets_waiting_again_not_game_start(self):
        # Regression test: find_active_game() starts resolving for PLAYER_1 the moment it joins a
        # waiting session, well before prepare()/begin_running() ever run for that session (those
        # only happen once a second player pairs into it). Reconnecting before that pairing used
        # to get a game_start built from the still-unprepared (no dealt hands) environment.
        with self.client.websocket_connect("/ws") as raw1:
            ws1 = QueuedWebSocket(raw1)
            login_with_deck(self.client, ws1, "alice")
            ws1.send_json({"type": "join"})
            ws1.receive_json()  # joined
            ws1.receive_json()  # waiting_for_opponent

            with self.client.websocket_connect("/ws") as raw1b:
                ws1b = QueuedWebSocket(raw1b)
                login(ws1b, "alice")

                # ws1 gets kicked (precedence) - same as the login-precedence test above.
                drain_for_type(ws1, "logged_out_elsewhere")

                joined = ws1b.receive_json()
                self.assertEqual(joined["type"], "joined")

                message = ws1b.receive_json()
                self.assertEqual(message["type"], "waiting_for_opponent")

    def test_leaving_the_queue_frees_the_account_and_a_relogin_lands_on_home(self):
        with self.client.websocket_connect("/ws") as raw1:
            ws1 = QueuedWebSocket(raw1)
            login_with_deck(self.client, ws1, "alice")
            ws1.send_json({"type": "join"})
            ws1.receive_json()  # joined
            ws1.receive_json()  # waiting_for_opponent

            ws1.send_json({"type": "leave"})
            self.assertEqual(ws1.receive_json(), {"type": "left"})

            # The same connection is free to queue again, and gets a brand new game.
            ws1.send_json({"type": "join"})
            joined = ws1.receive_json()
            self.assertEqual(joined["type"], "joined")
            ws1.receive_json()  # waiting_for_opponent

        # A leave that already succeeded must not leave a ghost behind for a later login to
        # resume: log in fresh, leave again, then reconnect and expect no "joined" resend.
        with self.client.websocket_connect("/ws") as raw2:
            ws2 = QueuedWebSocket(raw2)
            login(ws2, "alice")
            self.assertEqual(ws2.receive_json()["type"], "joined")
            ws2.receive_json()  # waiting_for_opponent
            ws2.send_json({"type": "leave"})
            self.assertEqual(ws2.receive_json(), {"type": "left"})

        with self.client.websocket_connect("/ws") as raw3:
            ws3 = QueuedWebSocket(raw3)
            login(ws3, "alice")
            ws3.send_json({"type": "leave"})  # nothing to leave: ignored, no crash
            ws3.send_json({"type": "join"})
            self.assertEqual(ws3.receive_json()["type"], "joined")


if __name__ == "__main__":
    unittest.main()
