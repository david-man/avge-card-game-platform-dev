import unittest

from pydantic import ValidationError

from .. import protocol


class ParseClientMessageTests(unittest.TestCase):
    def test_parses_join(self):
        msg = protocol.parse_client_message({"type": "join"})
        self.assertIsInstance(msg, protocol.JoinMessage)

    def test_parses_login_with_username(self):
        msg = protocol.parse_client_message({"type": "login", "username": "alice"})
        self.assertIsInstance(msg, protocol.LoginMessage)
        assert isinstance(msg, protocol.LoginMessage)
        self.assertEqual(msg.username, "alice")
        self.assertIsNone(msg.auth_token)

    def test_parses_login_with_auth_token(self):
        msg = protocol.parse_client_message({"type": "login", "auth_token": "tok"})
        self.assertIsInstance(msg, protocol.LoginMessage)
        assert isinstance(msg, protocol.LoginMessage)
        self.assertEqual(msg.auth_token, "tok")
        self.assertIsNone(msg.username)

    def test_login_with_neither_field_still_parses(self):
        # Both fields are optional at the parse level - ws_routes.py is what actually rejects a
        # login that resolves to no account, not this parser.
        msg = protocol.parse_client_message({"type": "login"})
        self.assertIsInstance(msg, protocol.LoginMessage)

    def test_parses_concede(self):
        msg = protocol.parse_client_message({"type": "concede"})
        self.assertIsInstance(msg, protocol.ConcedeMessage)

    def test_parses_io_response(self):
        msg = protocol.parse_client_message({
            "type": "io_response", "request_id": "r1", "payload": {"value": 3},
        })
        self.assertIsInstance(msg, protocol.IoResponseMessage)
        assert isinstance(msg, protocol.IoResponseMessage)
        self.assertEqual(msg.request_id, "r1")
        self.assertEqual(msg.payload, {"value": 3})

    def test_rejects_unknown_type(self):
        with self.assertRaises(ValueError):
            protocol.parse_client_message({"type": "not_a_real_message"})

    def test_rejects_missing_type(self):
        with self.assertRaises(ValueError):
            protocol.parse_client_message({"payload": {}})

    def test_rejects_io_response_missing_payload(self):
        with self.assertRaises(ValidationError):
            protocol.parse_client_message({"type": "io_response", "request_id": "r1"})


class ServerMessageRoundtripTests(unittest.TestCase):
    def test_io_request_roundtrip(self):
        msg = protocol.IoRequestMessage(request_id="r1", io_type="Phase2IO", payload={"can_finish": True})
        dumped = msg.model_dump()
        self.assertEqual(dumped["type"], "io_request")
        restored = protocol.IoRequestMessage.model_validate(dumped)
        self.assertEqual(restored, msg)

    def test_io_request_retry_reason_defaults_to_none(self):
        msg = protocol.IoRequestMessage(request_id="r1", io_type="Phase2IO", payload={})
        self.assertIsNone(msg.retry_reason)

    def test_io_request_retry_reason_roundtrip(self):
        msg = protocol.IoRequestMessage(
            request_id="r1", io_type="Phase2IO", payload={}, retry_reason="Invalid response",
        )
        dumped = msg.model_dump()
        self.assertEqual(dumped["retry_reason"], "Invalid response")
        restored = protocol.IoRequestMessage.model_validate(dumped)
        self.assertEqual(restored, msg)

    def test_event_update_roundtrip(self):
        msg = protocol.EventUpdateMessage(io_type="HPChangeUpdate", payload={"magnitude": 20})
        dumped = msg.model_dump()
        self.assertEqual(dumped["type"], "event_update")
        restored = protocol.EventUpdateMessage.model_validate(dumped)
        self.assertEqual(restored, msg)

    def test_game_over_allows_null_winner(self):
        msg = protocol.GameOverMessage(winner=None, reason="both_disconnected")
        self.assertIsNone(msg.winner)

    def test_error_message_code_is_optional(self):
        msg = protocol.ErrorMessage(message="something went wrong")
        self.assertIsNone(msg.code)

    def test_logged_in_roundtrip(self):
        msg = protocol.LoggedInMessage(account_id="a1", username="alice", auth_token="tok")
        dumped = msg.model_dump()
        self.assertEqual(dumped["type"], "logged_in")
        self.assertEqual(protocol.LoggedInMessage.model_validate(dumped), msg)

    def test_logged_out_elsewhere_shape(self):
        msg = protocol.LoggedOutElsewhereMessage()
        self.assertEqual(msg.model_dump(), {"type": "logged_out_elsewhere"})


if __name__ == "__main__":
    unittest.main()
