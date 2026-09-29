import unittest

from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ...avge_abstracts.AVGEDeck import DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import User, ActionTypes
from ...core.EventCatalog import TransferCard
from ...engine.event import Packet
from ...testing.helpers import Dummy, core_listeners
from ..decks import CARDS_PER_DECK
from ..game_setup import perform_initial_setup
from ..io_adapter import NetworkIO


class TransferSourceCheckTests(unittest.IsolatedAsyncioTestCase):
    '''AVGETransferSourceCheck (core/CoreListeners.py) skips a TransferCard whose card is no
    longer in deck_from instead of letting TransferCard.act() raise ValueError (which ends the
    whole match with server_error). A skip must not fail or roll back the packet, and the rest of
    the packet must still run.'''

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
        await perform_initial_setup(self.env)

        self.player = self.env.players[User.PLAYER_1]
        self.hand = self.player.card_piles[DeckType.HAND]
        self.bench = self.player.card_piles[DeckType.BENCH]
        self.discard = self.player.card_piles[DeckType.DISCARD]

    async def _flush(self, events, calling_action=ActionTypes.PLAYER_CHOICE):
        _id = AVGEEngineID(None, calling_action, None)
        self.env.push_packet(Packet(_id, events(_id)))
        await self.env.engine.flush(lambda: False)

    async def test_stale_source_is_skipped_without_crashing_or_rejecting(self):
        card = self.hand.cards_holding[0]
        sent_before = len(self.sent)

        # Claims the card is in DISCARD when it is really in HAND - used to raise ValueError from
        # list.remove inside TransferCard.act and end the game.
        await self._flush(lambda _id: [
            TransferCard(_id, card, self.discard, self.bench, self.env),
        ])

        self.assertIn(card, self.hand.cards_holding)
        self.assertNotIn(card, self.bench.cards_holding)
        self.assertNotIn(card, self.discard.cards_holding)
        # A skipped event is never committed, so nothing is broadcast for it (and it isn't a
        # rejection either - no ActionRejectedUpdate).
        self.assertEqual(self.sent[sent_before:], [])

    async def test_skip_does_not_stop_the_rest_of_the_packet(self):
        stale = self.hand.cards_holding[0]
        good = self.hand.cards_holding[1]

        await self._flush(lambda _id: [
            TransferCard(_id, stale, self.discard, self.bench, self.env),
            TransferCard(_id, good, self.hand, self.bench, self.env),
        ])

        self.assertIn(stale, self.hand.cards_holding)
        self.assertIn(good, self.bench.cards_holding)
        self.assertNotIn(good, self.hand.cards_holding)

    async def test_skip_applies_to_engine_initiated_transfers_too(self):
        card = self.hand.cards_holding[0]

        await self._flush(lambda _id: [
            TransferCard(_id, card, self.bench, self.discard, self.env),
        ], calling_action=ActionTypes.ENV)

        self.assertIn(card, self.hand.cards_holding)
        self.assertNotIn(card, self.discard.cards_holding)

    async def test_normal_transfer_is_unchanged(self):
        card = self.hand.cards_holding[0]

        await self._flush(lambda _id: [
            TransferCard(_id, card, self.hand, self.bench, self.env),
        ])

        self.assertIn(card, self.bench.cards_holding)
        self.assertNotIn(card, self.hand.cards_holding)
