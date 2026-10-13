import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from .. import config as server_config
from ..app import create_app
from ._ws_test_utils import login_with_deck


class DisconnectForfeitIntegrationTests(unittest.TestCase):
    '''Real TestClient sockets - proves the disconnect -> grace timer -> forced game_over path is
    wired correctly end-to-end (WebSocketDisconnect caught by ws_routes.py's _message_loop calling
    session.detach()), not just that GameSession's timer logic works against a FakeTransport in
    isolation (already covered by test_session.py's ConnectionStateTests).'''

    def setUp(self):
        self._orig_grace = server_config.RECONNECT_GRACE_SECONDS
        server_config.RECONNECT_GRACE_SECONDS = 0.05
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        # Shared portal across every websocket_connect() in this test - see
        # test_full_game_two_fake_clients.py's setUp for why a bare TestClient(app) is unsafe:
        # without it, ws2's own per-connection event loop tears down when ws2 closes, silently
        # cancelling the disconnect-grace timer this exact test depends on before it can fire.
        self.client = TestClient(create_app(data_dir=Path(self._tmpdir.name)))
        self.client.__enter__()
        self.addCleanup(lambda: self.client.__exit__(None, None, None))

    def tearDown(self):
        server_config.RECONNECT_GRACE_SECONDS = self._orig_grace

    def test_opponent_disconnecting_and_not_returning_forfeits_to_the_other_player(self):
        with self.client.websocket_connect("/ws") as ws1:
            login_with_deck(self.client, ws1, "alice")
            ws1.send_json({"type": "join"})
            ws1.receive_json()  # joined
            ws1.receive_json()  # waiting_for_opponent

            with self.client.websocket_connect("/ws") as ws2:
                login_with_deck(self.client, ws2, "bob")
                ws2.send_json({"type": "join"})
                ws2.receive_json()  # joined
                ws2.receive_json()  # setup_start
                ws1.receive_json()  # setup_start
                # ws2 closes here (end of the inner `with` block) without conceding - PLAYER_2
                # just vanishes, exactly like a dropped connection in the real world.

            game_over = _drain_for_type(ws1, "game_over")

        self.assertEqual(game_over["reason"], "disconnect_timeout")
        self.assertEqual(game_over["winner"], "PLAYER_1")


def _drain_for_type(ws, expected_type: str, limit: int = 200) -> dict:
    for _ in range(limit):
        message = ws.receive_json()
        if message["type"] == expected_type:
            return message
    raise AssertionError(f"never received a {expected_type!r} message within {limit} reads")


if __name__ == "__main__":
    unittest.main()
