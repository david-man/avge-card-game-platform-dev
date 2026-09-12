import asyncio
import unittest

from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ...avge_abstracts.AVGEDeck import DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import User, ActionTypes, WinReasons
from ...engine.engine_io import IOException
from ...core.AVGEIOManager import (
    BroadcastIO, Phase2IO, AtkPhaseIO, GameEndIO, Notification, CardSelectionQuery,
    StringSelectionQuery, IntInput, D6Input, CoinflipData, Phase2Finish, Phase2ActivateAbility,
    Phase2CardMovement, Phase2EnergyAttach, Phase2PlayCard, TurnEndUpdate, ActionRejectedUpdate,
)
from ...testing.helpers import Dummy, core_listeners, put_into_play, bench
from .. import protocol
from .. import serialization
from ..io_adapter import NetworkIO


class FakeTransport:
    def __init__(self):
        self.sent: list[tuple[User, dict]] = []
        self.failed_users: list[User] = []
        self.fail_next = False

    async def send(self, user, message):
        if self.fail_next:
            self.fail_next = False
            raise ConnectionError("simulated transport failure")
        self.sent.append((user, message))

    async def on_failure(self, user):
        self.failed_users.append(user)


def _id() -> AVGEEngineID:
    return AVGEEngineID(None, ActionTypes.ENV, None)


class NetworkIOTestBase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.transport = FakeTransport()
        self.io = NetworkIO(self.transport.send, self.transport.on_failure)
        self.env = AVGEEnvironment(self.io, {
            User.PLAYER_1: [Dummy, Dummy],
            User.PLAYER_2: [Dummy],
        }, core_listeners())
        self.env.turn = User.PLAYER_1
        self.p1 = self.env.players[User.PLAYER_1]
        self.p2 = self.env.players[User.PLAYER_2]
        self.active = await put_into_play(self.env, self.p1)
        self.benched = await bench(self.env, self.p1)


class SendEnvelopeTests(NetworkIOTestBase):
    async def test_broadcast_envelope_shape(self):
        await self.io.send(User.PLAYER_1, BroadcastIO("hi", 5))
        self.assertEqual(len(self.transport.sent), 1)
        user, message = self.transport.sent[0]
        self.assertEqual(user, User.PLAYER_1)
        self.assertEqual(message["type"], "io_request")
        self.assertEqual(message["io_type"], "BroadcastIO")
        self.assertEqual(message["payload"], {"message": "hi", "timeout": 5})
        self.assertEqual(message["request_id"], self.io.current_request_id(User.PLAYER_1))

    async def test_card_selection_envelope_includes_wire_cards_and_ids(self):
        io_obj = CardSelectionQuery(
            User.PLAYER_1, "pick one", 1, [self.active, self.benched], [self.active, self.benched], False, False,
        )
        await self.io.send(User.PLAYER_1, io_obj)
        _, message = self.transport.sent[0]
        self.assertEqual(message["payload"]["allowed_selections"], [self.active.cardID, self.benched.cardID])
        self.assertEqual(len(message["payload"]["displayed_cards"]), 2)

    async def test_game_end_uses_game_over_envelope_not_io_request(self):
        self.env.winner = User.PLAYER_2
        self.env.win_reason = WinReasons.ALL_KOS
        await self.io.send(User.PLAYER_1, GameEndIO(User.PLAYER_1))
        _, message = self.transport.sent[0]
        self.assertEqual(message["type"], "game_over")
        self.assertEqual(message["winner"], User.PLAYER_2.name)
        self.assertEqual(message["reason"], WinReasons.ALL_KOS.value)
        self.assertNotIn("request_id", message)

    async def test_game_end_self_resolves_with_no_client_action(self):
        # GameEndIO is fire-and-forget just like the per-event update types - if this actually
        # required a client response, GameEnd.act()'s own asyncio.gather() would hang forever.
        result = await asyncio.wait_for(self.env.report(GameEndIO(User.PLAYER_1), _id()), timeout=1.0)
        self.assertIsNone(result)

    async def test_transport_failure_routes_to_on_transport_failure(self):
        self.transport.fail_next = True
        await self.io.send(User.PLAYER_1, BroadcastIO("hi", None))
        self.assertEqual(self.transport.failed_users, [User.PLAYER_1])
        self.assertEqual(self.transport.sent, [])


class FireAndForgetUpdateTests(NetworkIOTestBase):
    async def test_update_type_uses_event_update_envelope_not_io_request(self):
        await self.io.send(User.PLAYER_1, TurnEndUpdate(User.PLAYER_2, 3))
        self.assertEqual(len(self.transport.sent), 1)
        _, message = self.transport.sent[0]
        self.assertEqual(message["type"], "event_update")
        self.assertEqual(message["io_type"], "TurnEndUpdate")
        self.assertEqual(message["payload"], {"new_turn": User.PLAYER_2.name, "new_round": 3})
        self.assertNotIn("request_id", message)

    async def test_update_type_self_resolves_immediately_with_no_client_action(self):
        # ActionRejectedUpdate/TurnEndUpdate/etc. are broadcast (IOType[None], not UserIOType) -
        # if this actually required a client response, this would hang forever - it must not.
        result = await asyncio.wait_for(
            self.env.broadcast(ActionRejectedUpdate(User.PLAYER_1)), timeout=1.0,
        )
        self.assertIsNone(result)

    async def test_update_type_self_resolves_even_on_transport_failure(self):
        self.transport.fail_next = True
        result = await asyncio.wait_for(
            self.env.broadcast(ActionRejectedUpdate(User.PLAYER_1)), timeout=1.0,
        )
        self.assertIsNone(result)
        self.assertEqual(self.transport.failed_users, [User.PLAYER_1])

    async def test_action_rejected_payload_carries_reason_and_a_fresh_snapshot(self):
        await self.io.send(User.PLAYER_1, ActionRejectedUpdate(User.PLAYER_1, reason="No energy left on that card to move."))
        _, message = self.transport.sent[0]
        self.assertEqual(message["payload"]["rejected_for"], User.PLAYER_1.name)
        self.assertEqual(message["payload"]["reason"], "No energy left on that card to move.")
        self.assertEqual(message["payload"]["snapshot"], serialization.snapshot(self.env))

    async def test_action_rejected_reason_defaults_to_none(self):
        await self.io.send(User.PLAYER_1, ActionRejectedUpdate(User.PLAYER_1))
        _, message = self.transport.sent[0]
        self.assertIsNone(message["payload"]["reason"])


class AckOnlyBackstopTests(NetworkIOTestBase):
    async def test_broadcast_self_resolves_via_its_own_timeout(self):
        # BroadcastIO is not a UserIOType - it goes out via env.broadcast() to every player at
        # once, not env.report() to a single one. Nobody acks either player here, so both only
        # resolve via their own backstop timers.
        result = await asyncio.wait_for(self.env.broadcast(BroadcastIO("hi", 0.01)), timeout=1.0)
        self.assertIsNone(result)

    async def test_notification_self_resolves_via_backstop_when_no_timeout_given(self):
        # Notification carries timeout=None here - falls back to config.ACK_BACKSTOP_SECONDS.
        # Monkeypatch the module-level constant the adapter reads at send() time.
        from .. import config as server_config
        original = server_config.ACK_BACKSTOP_SECONDS
        server_config.ACK_BACKSTOP_SECONDS = 0.01
        try:
            result = await asyncio.wait_for(self.env.report(Notification(User.PLAYER_1, "hi", None), _id()), timeout=1.0)
        finally:
            server_config.ACK_BACKSTOP_SECONDS = original
        self.assertIsNone(result)

    async def test_real_ack_resolves_before_backstop(self):
        task = asyncio.ensure_future(self.env.broadcast(BroadcastIO("hi", 5)))
        await asyncio.sleep(0.01)  # let both concurrent _dispatch() calls reach `await future`
        await self.io.receive(User.PLAYER_1, {})
        await self.io.receive(User.PLAYER_2, {})
        result = await asyncio.wait_for(task, timeout=1.0)
        self.assertIsNone(result)


class DecisionRoundtripTests(NetworkIOTestBase):
    async def _roundtrip(self, io_obj, payload):
        task = asyncio.ensure_future(self.env.report(io_obj, _id()))
        await asyncio.sleep(0)
        await self.io.receive(User.PLAYER_1, payload)
        return await asyncio.wait_for(task, timeout=1.0)

    async def test_phase2_finish(self):
        result = await self._roundtrip(Phase2IO(User.PLAYER_1), {"kind": "finish"})
        self.assertEqual(result, Phase2Finish())

    async def test_phase2_activate_ability(self):
        result = await self._roundtrip(Phase2IO(User.PLAYER_1), {"kind": "activate_ability", "card_id": self.active.cardID})
        assert isinstance(result, Phase2ActivateAbility)
        self.assertIs(result.card, self.active)

    async def test_phase2_energy_attach_from_env(self):
        result = await self._roundtrip(
            Phase2IO(User.PLAYER_1),
            {"kind": "energy_attach", "token_from": "ENV", "token_to": self.active.cardID},
        )
        assert isinstance(result, Phase2EnergyAttach)
        self.assertIs(result.token_from, self.env)
        self.assertIs(result.token_to, self.active)

    async def test_phase2_card_movement(self):
        result = await self._roundtrip(
            Phase2IO(User.PLAYER_1),
            {
                "kind": "card_movement", "card_id": self.benched.cardID,
                "deck_from": {"owner": User.PLAYER_1.name, "deck_type": "BENCH"},
                "deck_to": {"owner": User.PLAYER_1.name, "deck_type": "ACTIVE_CARD"},
            },
        )
        assert isinstance(result, Phase2CardMovement)
        self.assertIs(result.card, self.benched)
        self.assertIs(result.deck_from, self.p1.card_piles[DeckType.BENCH])
        self.assertIs(result.deck_to, self.p1.card_piles[DeckType.ACTIVE_CARD])

    async def test_phase2_card_movement_to_stadium(self):
        # Regression test: the wire encoding for the STADIUM deck has owner=None (it has no
        # owning player - see io_adapter._wire_deck_ref) and _resolve_deck_field used to try
        # User[str(None)] before ever checking deck_type, rejecting every stadium reference.
        result = await self._roundtrip(
            Phase2IO(User.PLAYER_1),
            {
                "kind": "card_movement", "card_id": self.benched.cardID,
                "deck_from": {"owner": User.PLAYER_1.name, "deck_type": "BENCH"},
                "deck_to": {"owner": None, "deck_type": "STADIUM"},
            },
        )
        assert isinstance(result, Phase2CardMovement)
        self.assertIs(result.deck_to, self.env.stadium_cardholder)

    async def test_atk_phase_skip(self):
        result = await self._roundtrip(AtkPhaseIO(User.PLAYER_1), {"action": "SKIP"})
        self.assertEqual(result, ActionTypes.SKIP)

    async def test_atk_phase_invalid_action_raises_and_retries(self):
        task = asyncio.ensure_future(self.env.report(AtkPhaseIO(User.PLAYER_1), _id()))
        await asyncio.sleep(0)
        await self.io.receive(User.PLAYER_1, {"action": "NOT_REAL"})
        # bad input triggers retry(), not a resolved future - answer correctly this time
        await self.io.receive(User.PLAYER_1, {"action": "SKIP"})
        result = await asyncio.wait_for(task, timeout=1.0)
        self.assertEqual(result, ActionTypes.SKIP)

    async def test_retry_message_validates_against_the_protocol_schema_and_carries_the_error(self):
        # The regression test for the io_request/retry_reason schema drift: retry()'s emitted
        # message must actually be (not just resemble) a valid protocol.IoRequestMessage.
        task = asyncio.ensure_future(self.env.report(AtkPhaseIO(User.PLAYER_1), _id()))
        await asyncio.sleep(0)
        await self.io.receive(User.PLAYER_1, {"action": "NOT_REAL"})
        _, retry_message = self.transport.sent[-1]
        validated = protocol.IoRequestMessage.model_validate(retry_message)
        self.assertIsNotNone(validated.retry_reason)
        self.assertIn("NOT_REAL", validated.retry_reason)
        await self.io.receive(User.PLAYER_1, {"action": "SKIP"})
        await asyncio.wait_for(task, timeout=1.0)

    async def test_card_selection_query(self):
        io_obj = CardSelectionQuery(
            User.PLAYER_1, "pick one", 1, [self.active, self.benched], [self.active, self.benched], False, False,
        )
        result = await self._roundtrip(io_obj, {"selected_ids": [self.benched.cardID]})
        self.assertEqual(result, [self.benched])

    async def test_card_selection_rejects_id_outside_allowed_selections(self):
        io_obj = CardSelectionQuery(User.PLAYER_1, "pick one", 1, [self.active], [self.active, self.benched], False, False)
        with self.assertRaises(IOException):
            self.io.deserialize(io_obj, {"selected_ids": [self.benched.cardID]})

    async def test_card_selection_rejects_non_string_elements_cleanly(self):
        # Regression test: selected_ids elements used to go straight into a set-membership check
        # (`raw_id not in allowed_ids`) with no type check, so a non-hashable element (a dict or
        # list instead of a card id string) raised a bare TypeError instead of IOException - which
        # meant it wasn't caught by the base receive()'s retry-on-IOException handling and instead
        # escaped as an "unexpected" server error, ending the whole connection over one malformed
        # response rather than the harmless retry every other invalid selection gets.
        io_obj = CardSelectionQuery(User.PLAYER_1, "pick one", 1, [self.active], [self.active, self.benched], False, False)
        with self.assertRaises(IOException):
            self.io.deserialize(io_obj, {"selected_ids": [{"not": "a card id"}]})
        with self.assertRaises(IOException):
            self.io.deserialize(io_obj, {"selected_ids": [["nested", "list"]]})

    async def test_card_selection_rejects_empty_when_not_allowed_none(self):
        io_obj = CardSelectionQuery(User.PLAYER_1, "pick one", 1, [self.active], [self.active], False, False)
        with self.assertRaises(IOException):
            self.io.deserialize(io_obj, {"selected_ids": []})

    async def test_card_selection_allows_empty_when_allows_none(self):
        io_obj = CardSelectionQuery(User.PLAYER_1, "pick one", 1, [self.active], [self.active], True, False)
        result = self.io.deserialize(io_obj, {"selected_ids": []})
        self.assertEqual(result, [])

    async def test_string_selection_query(self):
        io_obj = StringSelectionQuery(User.PLAYER_1, "pick", 1, ["a", "b"], ["a", "b"], False, False)
        result = await self._roundtrip(io_obj, {"selected": ["b"]})
        self.assertEqual(result, ["b"])

    async def test_int_input_in_range(self):
        result = await self._roundtrip(IntInput(User.PLAYER_1, "n", 1, 5), {"value": 3})
        self.assertEqual(result, 3)

    async def test_int_input_out_of_range_raises(self):
        io_obj = IntInput(User.PLAYER_1, "n", 1, 5)
        with self.assertRaises(IOException):
            self.io.deserialize(io_obj, {"value": 10})

    async def test_d6_input(self):
        result = await self._roundtrip(D6Input(User.PLAYER_1, "roll"), {"value": 4})
        self.assertEqual(result, 4)

    async def test_d6_input_out_of_range_raises(self):
        with self.assertRaises(IOException):
            self.io.deserialize(D6Input(User.PLAYER_1, "roll"), {"value": 7})

    async def test_coinflip(self):
        result = await self._roundtrip(CoinflipData(User.PLAYER_1, "flip"), {"value": 1})
        self.assertEqual(result, 1)

    async def test_coinflip_invalid_value_raises(self):
        with self.assertRaises(IOException):
            self.io.deserialize(CoinflipData(User.PLAYER_1, "flip"), {"value": 2})


if __name__ == "__main__":
    unittest.main()
