import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from ..app import create_app
from ..matchmaker import Matchmaker
from ._ws_test_utils import login, login_with_deck


class NoDeckJoinTests(unittest.TestCase):
    '''Proves the server-side half of "Play requires a selected deck" - ws_routes.py's
    _resolve_selected_deck() must reject a join before matchmaker.join() is ever called, not just
    rely on the frontend disabling its own Play button.'''

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.app = create_app(data_dir=Path(self._tmpdir.name))
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.addCleanup(lambda: self.client.__exit__(None, None, None))

    def test_joining_with_no_selected_deck_is_rejected_and_leaks_no_session(self):
        matchmaker: Matchmaker = self.app.state.matchmaker
        with self.client.websocket_connect("/ws") as ws:
            login(ws, "alice")  # no deck ever saved/selected
            ws.send_json({"type": "join"})
            response = ws.receive_json()
            self.assertEqual(response["type"], "error")
            self.assertEqual(response["code"], "no_deck_selected")
        self.assertEqual(matchmaker.sessions, {})

    def test_after_selecting_a_deck_the_same_join_succeeds(self):
        with self.client.websocket_connect("/ws") as ws:
            login_with_deck(self.client, ws, "alice")
            ws.send_json({"type": "join"})
            response = ws.receive_json()
            self.assertEqual(response["type"], "joined")


if __name__ == "__main__":
    unittest.main()
