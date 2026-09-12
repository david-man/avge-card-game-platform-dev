import unittest

from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ...avge_abstracts.AVGEDeck import DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import User, ActionTypes, INITIAL_HAND_SIZE
from ...core.EventCatalog import AVGECardHPChangeEvent, AVGEEnergyTransfer
from ...avge_abstracts.AVGECard import CardType
from ...constants import AVGEAttributeModifier
from ...engine.event import Packet
from ...testing.helpers import Dummy, TestIO, core_listeners
from .. import serialization
from ..decks import CARDS_PER_DECK
from ..game_setup import perform_initial_setup
from ..io_adapter import NetworkIO
from ...core.AVGEIOManager import HPChangeUpdate


class PerformInitialSetupTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.sent: list[tuple[User, dict]] = []

        async def send_message(user, message):
            self.sent.append((user, message))

        async def on_failure(user):
            pass

        self.io = NetworkIO(send_message, on_failure)
        self.env = AVGEEnvironment(self.io, {
            User.PLAYER_1: [Dummy] * CARDS_PER_DECK,
            User.PLAYER_2: [Dummy] * CARDS_PER_DECK,
        }, core_listeners())
        self.env.turn = User.PLAYER_1

    async def test_deals_active_and_hand_for_both_players(self):
        await perform_initial_setup(self.env)
        for user in (User.PLAYER_1, User.PLAYER_2):
            player = self.env.players[user]
            self.assertEqual(len(player.card_piles[DeckType.ACTIVE_CARD]), 1)
            self.assertEqual(len(player.card_piles[DeckType.HAND]), INITIAL_HAND_SIZE)
            self.assertEqual(len(player.card_piles[DeckType.DECK]), CARDS_PER_DECK - 1 - INITIAL_HAND_SIZE)

    async def test_dealt_cards_are_distinct(self):
        await perform_initial_setup(self.env)
        player = self.env.players[User.PLAYER_1]
        active = player.card_piles[DeckType.ACTIVE_CARD].cards_holding[0]
        hand_ids = {c.cardID for c in player.card_piles[DeckType.HAND].cards_holding}
        self.assertNotIn(active.cardID, hand_ids)
        self.assertEqual(len(hand_ids), INITIAL_HAND_SIZE)

    async def test_wires_on_event_committed_to_a_real_broadcast(self):
        await perform_initial_setup(self.env)
        self.assertIsNotNone(self.env.engine.on_event_committed)
        self.assertIsNotNone(self.env.engine.on_packet_failed)

        target = self.env.players[User.PLAYER_1].card_piles[DeckType.ACTIVE_CARD].cards_holding[0]
        _id = AVGEEngineID(None, ActionTypes.ENV, None)
        self.env.push_packet(Packet(_id, [AVGECardHPChangeEvent(
            _id, target, 15, AVGEAttributeModifier.SUBSTRACTIVE, CardType.ALL, self.env,
        )]))
        await self.env.engine.flush(lambda: False)

        updates = [m for _, m in self.sent if m.get("io_type") == "HPChangeUpdate"]
        self.assertEqual(len(updates), 2)  # broadcast to both players
        self.assertEqual(updates[0]["type"], "event_update")
        self.assertEqual(updates[0]["payload"]["magnitude"], 15)

    async def test_regulate_fail_broadcasts_the_regulators_reason_and_a_resync_snapshot(self):
        '''AVGETokenTransferCheck (core/CoreListeners.py) REGULATE_FAILs an AVGEEnergyTransfer
        when the source card has no energy to move - the exact "attach energy with none
        available" case from the review. Confirms the live per-event broadcast (none here, since
        nothing committed before the failure) plus the single combined ActionRejectedUpdate
        carrying both the regulator's own reason and a post-rollback state snapshot.'''
        await perform_initial_setup(self.env)
        active = self.env.players[User.PLAYER_1].card_piles[DeckType.ACTIVE_CARD].cards_holding[0]
        active.energy_tokens = []

        _id = AVGEEngineID(None, ActionTypes.ENV, None)
        self.env.push_packet(Packet(_id, [AVGEEnergyTransfer(_id, active, self.env, self.env)]))
        await self.env.engine.flush(lambda: False)

        rejected = [m for _, m in self.sent if m.get("io_type") == "ActionRejectedUpdate"]
        self.assertEqual(len(rejected), 2)  # broadcast to both players
        payload = rejected[0]["payload"]
        self.assertEqual(payload["reason"], "No energy left on that card to move.")
        self.assertEqual(payload["snapshot"], serialization.snapshot(self.env))

    async def test_extra_on_packet_failed_runs_alongside_the_broadcast(self):
        '''Regression test for the hook-chaining refactor: on_packet_failed used to get set here
        and then wrapped a second time by GameSession._wire_packet_rejection_logging(), with
        correctness depending on call order between two separate files. extra_on_packet_failed is
        now composed in at the single call site instead - this proves both the broadcast and a
        caller-supplied extra hook actually fire, in order, on the same rejection.'''
        calls: list[str] = []

        async def extra(packet: Packet) -> None:
            calls.append("extra")

        await perform_initial_setup(self.env, extra_on_packet_failed=extra)
        active = self.env.players[User.PLAYER_1].card_piles[DeckType.ACTIVE_CARD].cards_holding[0]
        active.energy_tokens = []

        _id = AVGEEngineID(None, ActionTypes.ENV, None)
        self.env.push_packet(Packet(_id, [AVGEEnergyTransfer(_id, active, self.env, self.env)]))
        await self.env.engine.flush(lambda: False)

        rejected = [m for _, m in self.sent if m.get("io_type") == "ActionRejectedUpdate"]
        self.assertEqual(len(rejected), 2)  # the broadcast still ran
        self.assertEqual(calls, ["extra"])  # and the extra hook ran too


if __name__ == "__main__":
    unittest.main()
