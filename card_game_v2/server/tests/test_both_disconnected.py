import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from ..app import create_app
from ..matchmaker import Matchmaker
from ._ws_test_utils import QueuedWebSocket, login_with_deck


class BothDisconnectedIntegrationTests(unittest.TestCase):
    '''Real TestClient sockets - proves that both players vanishing is cleanly abandoned (no
    winner, no unhandled task exception) end-to-end, not just that GameSession._abandon() works
    against a FakeTransport in isolation (already covered by test_session.py's
    ConnectionStateTests.test_both_disconnected_abandons_with_no_winner). Abandonment is now
    immediate (no grace period to wait out), so this only needs a short bounded poll to absorb
    normal async scheduling/dispatch latency, not a long one.'''

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.app = create_app(data_dir=Path(self._tmpdir.name))
        # Shared portal across every websocket_connect() in this test - see
        # test_full_game_two_fake_clients.py's setUp for why a bare TestClient(app) is unsafe.
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.addCleanup(lambda: self.client.__exit__(None, None, None))

    def test_both_players_vanishing_abandons_the_session_with_no_winner(self):
        matchmaker: Matchmaker = self.app.state.matchmaker

        with self.client.websocket_connect("/ws") as raw1, self.client.websocket_connect("/ws") as raw2:
            ws1, ws2 = QueuedWebSocket(raw1), QueuedWebSocket(raw2)
            login_with_deck(self.client, ws1, "alice")
            ws1.send_json({"type": "join"})
            joined1 = ws1.receive_json()
            ws1.receive_json()  # waiting_for_opponent

            login_with_deck(self.client, ws2, "bob")
            ws2.send_json({"type": "join"})
            ws2.receive_json()  # joined
            ws2.receive_json()  # setup_start
            ws1.receive_json()  # setup_start
            # Both sockets close here (end of the `with` block) - nobody concedes, nobody comes
            # back, exactly like both tabs being closed in the real world.

        game_id = joined1["game_id"]
        self.assertIn(game_id, matchmaker.sessions)

        deadline = time.monotonic() + 1.0
        while game_id in matchmaker.sessions and time.monotonic() < deadline:
            time.sleep(0.02)

        self.assertNotIn(game_id, matchmaker.sessions, "session was never abandoned/deregistered")


if __name__ == "__main__":
    unittest.main()
