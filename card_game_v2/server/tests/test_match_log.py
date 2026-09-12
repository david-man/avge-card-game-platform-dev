import json
import unittest

from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import ActionTypes, User
from ...core.AVGEIOManager import Notification, Phase2Finish
from ...testing.helpers import Dummy, TestIO, core_listeners, put_into_play
from ..io_adapter import NetworkIO
from ..match_log import _safe_json, serialize_history_records


async def _noop_send(user, message):
    pass


async def _noop_failure(user):
    pass


class SafeJsonTests(unittest.TestCase):
    def test_primitives_pass_through(self):
        self.assertEqual(_safe_json(None), None)
        self.assertEqual(_safe_json("x"), "x")
        self.assertEqual(_safe_json(5), 5)
        self.assertEqual(_safe_json(1.5), 1.5)
        self.assertEqual(_safe_json(True), True)

    def test_list_and_dict_recurse(self):
        self.assertEqual(_safe_json([1, "a", None]), [1, "a", None])
        self.assertEqual(_safe_json({"a": 1, "b": [1, 2]}), {"a": 1, "b": [1, 2]})

    def test_enum_uses_name(self):
        self.assertEqual(_safe_json(User.PLAYER_1), "PLAYER_1")

    def test_unknown_dataclass_falls_back_to_type_tagged_field_dump(self):
        self.assertEqual(_safe_json(Phase2Finish()), {"_type": "Phase2Finish"})

    def test_json_dumps_round_trips(self):
        json.dumps(_safe_json({"a": [User.PLAYER_2, Phase2Finish()]}))


class SerializeHistoryRecordsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.env = AVGEEnvironment(TestIO(), {
            User.PLAYER_1: [Dummy, Dummy],
            User.PLAYER_2: [Dummy, Dummy],
        }, core_listeners())
        self.io = NetworkIO(_noop_send, _noop_failure)

    async def test_committed_event_is_serialized_via_event_broadcasting(self):
        await put_into_play(self.env, self.env.players[User.PLAYER_1])
        records = serialize_history_records(self.env, self.io)
        moved = [r for r in records if r.get("event_type") == "TransferCard"]
        self.assertGreater(len(moved), 0)
        entry = moved[0]
        self.assertEqual(entry["kind"], "event")
        self.assertEqual(entry["status"], "IMMUTABLE")
        self.assertIn("card", entry["payload"])
        self.assertIn("deck_from", entry["payload"])
        self.assertIn("deck_to", entry["payload"])
        json.dumps(records)  # must be fully JSON-serializable

    async def test_io_request_response_is_serialized(self):
        _id = AVGEEngineID(None, ActionTypes.ENV, None)
        await self.env.report(Notification(User.PLAYER_1, "hi", None), _id)
        records = serialize_history_records(self.env, self.io)
        io_records = [r for r in records if r["kind"] == "io"]
        self.assertEqual(len(io_records), 1)
        entry = io_records[0]
        self.assertEqual(entry["io_type"], "Notification")
        self.assertEqual(entry["request"], {"message": "hi", "timeout": None})
        self.assertIsNone(entry["response"])
        json.dumps(records)


if __name__ == "__main__":
    unittest.main()
