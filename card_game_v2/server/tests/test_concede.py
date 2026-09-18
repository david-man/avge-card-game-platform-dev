import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from ..app import create_app
from ._ws_test_utils import login_with_deck


class ConcedeIntegrationTests(unittest.TestCase):
    '''Real TestClient sockets (not the FakeTransport used by test_session.py's unit tests) -
    proves concede is wired correctly end-to-end through ws_routes.py, not just that
    GameSession.force_end() itself works in isolation.'''

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        # Shared portal across every websocket_connect() in this test - see
        # test_full_game_two_fake_clients.py's setUp for why a bare TestClient(app) is unsafe.
        self.client = TestClient(create_app(data_dir=Path(self._tmpdir.name)))
        self.client.__enter__()
        self.addCleanup(lambda: self.client.__exit__(None, None, None))

    def test_concede_produces_immediate_deterministic_game_over_for_both_sides(self):
        with self.client.websocket_connect("/ws") as ws1:
            login_with_deck(self.client, ws1, "alice")
            ws1.send_json({"type": "join"})
            ws1.receive_json()  # joined
            ws1.receive_json()  # waiting_for_opponent

            with self.client.websocket_connect("/ws") as ws2:
                login_with_deck(self.client, ws2, "bob")
                ws2.send_json({"type": "join"})
                ws2.receive_json()  # joined
                ws2.receive_json()  # game_start
                ws1.receive_json()  # game_start

                ws2.send_json({"type": "concede"})

                game_over_1 = _drain_for_type(ws1, "game_over")
                game_over_2 = _drain_for_type(ws2, "game_over")

        self.assertEqual(game_over_1, game_over_2)
        self.assertEqual(game_over_1["reason"], "concede")
        self.assertEqual(game_over_1["winner"], "PLAYER_1")  # PLAYER_2 conceded -> PLAYER_1 wins


def _drain_for_type(ws, expected_type: str, limit: int = 200) -> dict:
    for _ in range(limit):
        message = ws.receive_json()
        if message["type"] == expected_type:
            return message
    raise AssertionError(f"never received a {expected_type!r} message within {limit} reads")


if __name__ == "__main__":
    unittest.main()
