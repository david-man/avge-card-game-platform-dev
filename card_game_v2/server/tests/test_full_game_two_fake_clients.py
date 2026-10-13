import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from ..app import create_app
from ._ws_test_utils import QueuedWebSocket, drain_for_type, first_io_request, login_with_deck, submit_default_setup


class FullGameWiringTests(unittest.TestCase):
    '''Integration test using Starlette's TestClient (synchronous, no real network) - proves the
    wiring (routing, matchmaking pairing, request_id correlation) is correct end-to-end. Business
    logic (validation, translation, grace timers, etc.) is already covered by the unit-level
    tests in test_io_adapter.py/test_session.py/test_matchmaker.py/test_event_broadcasting.py -
    this test deliberately stays short rather than trying to play a full game to natural
    completion via real HP values, which would be slow and not add real coverage.'''

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.app = create_app(data_dir=Path(self._tmpdir.name))
        # Used as a context manager (not just TestClient(self.app)) so every websocket_connect()
        # call in this test shares ONE portal/event loop, matching production's single shared
        # asyncio loop - otherwise each connection gets its own independent event loop, and a
        # GameSession background task (or a disconnect-grace timer) created from inside one
        # connection's handler gets silently cancelled the moment THAT connection's own portal
        # tears down, even though the session logically spans both players and must outlive either
        # one's individual socket.
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.addCleanup(lambda: self.client.__exit__(None, None, None))

    def test_two_clients_complete_setup_before_game_start(self):
        with self.client.websocket_connect("/ws") as ws1:
            login_with_deck(self.client, ws1, "alice")
            ws1.send_json({"type": "join"})
            joined1 = ws1.receive_json()
            self.assertEqual(joined1["type"], "joined")
            self.assertEqual(joined1["user"], "PLAYER_1")
            game_id = joined1["game_id"]

            waiting = ws1.receive_json()
            self.assertEqual(waiting["type"], "waiting_for_opponent")

            with self.client.websocket_connect("/ws") as ws2:
                login_with_deck(self.client, ws2, "bob")
                ws2.send_json({"type": "join"})
                joined2 = ws2.receive_json()
                self.assertEqual(joined2["type"], "joined")
                self.assertEqual(joined2["user"], "PLAYER_2")
                self.assertEqual(joined2["game_id"], game_id)

                setup2 = ws2.receive_json()
                setup1 = ws1.receive_json()
                self.assertEqual(setup2["type"], "setup_start")
                self.assertEqual(setup1["type"], "setup_start")
                submit_default_setup(ws1, setup1, "PLAYER_1")
                submit_default_setup(ws2, setup2, "PLAYER_2")
                self.assertEqual(_drain_raw_for_type(ws1, "game_start")["snapshot"]["round"], 0)
                self.assertEqual(_drain_raw_for_type(ws2, "game_start")["snapshot"]["round"], 0)

    def test_io_request_response_roundtrip_and_concede(self):
        with self.client.websocket_connect("/ws") as raw1, self.client.websocket_connect("/ws") as raw2:
            ws1, ws2 = QueuedWebSocket(raw1), QueuedWebSocket(raw2)

            login_with_deck(self.client, ws1, "alice")
            ws1.send_json({"type": "join"})
            ws1.receive_json()  # joined
            ws1.receive_json()  # waiting_for_opponent

            login_with_deck(self.client, ws2, "bob")
            ws2.send_json({"type": "join"})
            ws2.receive_json()  # joined
            setup2 = ws2.receive_json()  # setup_start
            setup1 = ws1.receive_json()  # setup_start
            submit_default_setup(ws1, setup1, "PLAYER_1")
            submit_default_setup(ws2, setup2, "PLAYER_2")
            drain_for_type(ws1, "game_start")
            drain_for_type(ws2, "game_start")

            # Whoever env.turn actually is receives the first io_request (Phase2IO, since round 0
            # skips attacking) - which player that is depends on the random per-game deck shuffle,
            # so poll both sockets rather than assuming it's a particular one.
            responder, request = first_io_request(ws1, ws2)
            self.assertEqual(request["io_type"], "Phase2IO")
            responder.send_json({
                "type": "io_response", "request_id": request["request_id"], "payload": {"kind": "finish"},
            })

            # End the game deterministically rather than trying to play to a natural KO.
            ws1.send_json({"type": "concede"})
            game_over_1 = drain_for_type(ws1, "game_over")
            game_over_2 = drain_for_type(ws2, "game_over")
            self.assertEqual(game_over_1["reason"], "concede")
            self.assertEqual(game_over_2, game_over_1)


def _drain_raw_for_type(ws, expected_type: str) -> dict:
    for _ in range(20):
        message = ws.receive_json()
        if message["type"] == expected_type:
            return message
    raise AssertionError(f"never received {expected_type}")


if __name__ == "__main__":
    unittest.main()
