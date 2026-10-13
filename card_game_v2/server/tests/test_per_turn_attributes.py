import asyncio
import contextlib
import unittest

from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment, EnergyToken
from ...avge_abstracts.AVGEDeck import DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import User, ActionTypes, AVGEPlayerAttribute
from ...core.EventCatalog import TransferCard, Phase2
from ...core.AVGEIOManager import Phase2IO
from ...engine.event import Packet
from ...testing.helpers import Dummy, core_listeners
from ..decks import CARDS_PER_DECK
from ..game_setup import perform_initial_setup
from ..io_adapter import NetworkIO


class PerTurnAttributeDecrementTests(unittest.IsolatedAsyncioTestCase):
    '''Regression tests for a real gap: AVGETransferValidityCheck/AVGETokenTransferCheck
    (core/CoreListeners.py) only ever REJECT once SWAP_REMAINING_IN_TURN/
    ENERGY_ADD_REMAINING_IN_TURN hit 0 - nothing decremented either one after a successful
    swap/energy-attach, so a player could otherwise perform either action any number of times in
    one turn. These drive a real Phase2 event through the engine end-to-end (not just
    deserialization, like DecisionRoundtripTests in test_io_adapter.py) since the fix lives in
    EventCatalog.py's Phase2 response dispatch, not the IO layer.'''

    async def asyncSetUp(self):
        self.sent: list[tuple[User, dict]] = []

        async def send_message(user, message):
            self.sent.append((user, message))
            if message.get("io_type") == "Notification":
                asyncio.create_task(self.io.receive(user, {}))

        async def on_failure(user):
            pass

        self.io = NetworkIO(send_message, on_failure)
        self.env = AVGEEnvironment(self.io, {
            User.PLAYER_1: [Dummy] * CARDS_PER_DECK,
            User.PLAYER_2: [Dummy] * CARDS_PER_DECK,
        }, core_listeners())
        self.env.turn = User.PLAYER_1
        await perform_initial_setup(self.env)
        self.player = self.env.players[User.PLAYER_1]
        self._flush_task: asyncio.Task[None] | None = None

    async def asyncTearDown(self):
        if self._flush_task is not None and not self._flush_task.done():
            self._flush_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._flush_task

    async def _start_phase2_loop(self) -> None:
        _id = AVGEEngineID(None, ActionTypes.ENV, None)
        self.env.push_packet(Packet(_id, [Phase2(_id, self.env)]))
        self._flush_task = asyncio.ensure_future(self.env.engine.flush(lambda: False))

    async def _next_request_id(self, previous_id: str | None) -> str:
        for _ in range(200):
            current = self.io.current_request_id(User.PLAYER_1)
            pending = self.io.pending.get(User.PLAYER_1)
            if (
                current is not None
                and current != previous_id
                and pending is not None
                and isinstance(pending.io_obj, Phase2IO)
            ):
                return current
            await asyncio.sleep(0)
        raise AssertionError("no new Phase2IO request appeared for PLAYER_1")

    async def test_swap_decrements_and_blocks_a_second_swap_same_turn(self):
        hand_cards = self.player.card_piles[DeckType.HAND].cards_holding[:2]
        _id = AVGEEngineID(None, ActionTypes.ENV, None)
        for card in hand_cards:
            self.env.push_packet(Packet(_id, [TransferCard(
                _id, card, self.player.card_piles[DeckType.HAND],
                self.player.card_piles[DeckType.BENCH], self.env,
            )]))
        await self.env.engine.flush(lambda: False)
        first_bench, second_bench = hand_cards
        active = self.player.card_piles[DeckType.ACTIVE_CARD].cards_holding[0]
        for card in (active, first_bench, second_bench):
            card.energy_tokens = [EnergyToken(f"{card.cardID}_e") for _ in range(5)]

        self.assertEqual(self.player.attributes[AVGEPlayerAttribute.SWAP_REMAINING_IN_TURN], 1)

        await self._start_phase2_loop()
        req1 = await self._next_request_id(None)
        await self.io.receive(User.PLAYER_1, {
            "kind": "card_movement", "card_id": first_bench.cardID,
            "deck_from": {"owner": "PLAYER_1", "deck_type": "BENCH"},
            "deck_to": {"owner": "PLAYER_1", "deck_type": "ACTIVE_CARD"},
        })

        req2 = await self._next_request_id(req1)
        self.assertIs(self.player.card_piles[DeckType.ACTIVE_CARD].cards_holding[0], first_bench)
        self.assertEqual(self.player.attributes[AVGEPlayerAttribute.SWAP_REMAINING_IN_TURN], 0)

        await self.io.receive(User.PLAYER_1, {
            "kind": "card_movement", "card_id": second_bench.cardID,
            "deck_from": {"owner": "PLAYER_1", "deck_type": "BENCH"},
            "deck_to": {"owner": "PLAYER_1", "deck_type": "ACTIVE_CARD"},
        })
        await self._next_request_id(req2)

        # Second swap must be rejected - active is still first_bench, second_bench never moved.
        self.assertIs(self.player.card_piles[DeckType.ACTIVE_CARD].cards_holding[0], first_bench)
        self.assertIn(second_bench, self.player.card_piles[DeckType.BENCH].cards_holding)
        rejected = [m for _, m in self.sent if m.get("io_type") == "ActionRejectedUpdate"]
        self.assertTrue(len(rejected) > 0)
        self.assertIn(
            "You've already swapped your active character this turn.",
            [m["payload"]["message"] for _, m in self.sent if m.get("io_type") == "Notification"],
        )

    async def test_energy_attach_decrements_and_blocks_a_second_attach_same_turn(self):
        active = self.player.card_piles[DeckType.ACTIVE_CARD].cards_holding[0]
        active.energy_tokens = []
        self.assertEqual(self.player.attributes[AVGEPlayerAttribute.ENERGY_ADD_REMAINING_IN_TURN], 1)

        await self._start_phase2_loop()
        req1 = await self._next_request_id(None)
        await self.io.receive(User.PLAYER_1, {
            "kind": "energy_attach", "token_from": "ENV", "token_to": active.cardID,
        })

        req2 = await self._next_request_id(req1)
        self.assertEqual(len(active.energy_tokens), 1)
        self.assertEqual(self.player.attributes[AVGEPlayerAttribute.ENERGY_ADD_REMAINING_IN_TURN], 0)

        await self.io.receive(User.PLAYER_1, {
            "kind": "energy_attach", "token_from": "ENV", "token_to": active.cardID,
        })
        await self._next_request_id(req2)

        # Second attach must be rejected - still exactly 1 energy token, not 2.
        self.assertEqual(len(active.energy_tokens), 1)
        rejected = [m for _, m in self.sent if m.get("io_type") == "ActionRejectedUpdate"]
        self.assertTrue(len(rejected) > 0)
        self.assertIn(
            "You've already attached energy this turn.",
            [m["payload"]["message"] for _, m in self.sent if m.get("io_type") == "Notification"],
        )


if __name__ == "__main__":
    unittest.main()
