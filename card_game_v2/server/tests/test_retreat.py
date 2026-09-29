import unittest

from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment, EnergyToken
from ...avge_abstracts.AVGEDeck import DeckType
from ...avge_abstracts.AVGEID import AVGEEngineID
from ...constants import User, ActionTypes
from ...core.EventCatalog import TransferCard
from ...engine.event import Packet
from ...testing.helpers import Dummy, core_listeners
from ..decks import CARDS_PER_DECK
from ..game_setup import perform_initial_setup
from ..io_adapter import NetworkIO


class RetreatCostTests(unittest.IsolatedAsyncioTestCase):
    '''AVGETransferValidityCheck (core/CoreListeners.py) used to compare the active card's energy
    against the INCOMING bench card's retreat_cost instead of the OUTGOING active card's own -
    retreat_cost must always be paid by whichever character is actually leaving the active slot.
    These drive the real two-TransferCard packet shape Phase2CardMovement produces
    (core/EventCatalog.py) directly, since none of the existing retreat_cost tests under
    card_game_v2/testing/ happened to exercise this BENCH->ACTIVE_CARD code path.'''

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
        self.active = self.player.card_piles[DeckType.ACTIVE_CARD].cards_holding[0]
        self.incoming = self.player.card_piles[DeckType.HAND].cards_holding[0]

        # Retreating always swaps with a benched character - move the future incoming card from
        # hand to bench first (perform_initial_setup only deals active + hand).
        _id = AVGEEngineID(None, ActionTypes.ENV, None)
        self.env.push_packet(Packet(_id, [TransferCard(
            _id, self.incoming, self.player.card_piles[DeckType.HAND],
            self.player.card_piles[DeckType.BENCH], self.env,
        )]))
        await self.env.engine.flush(lambda: False)

    def _retreat_packet(self) -> Packet:
        '''The exact two-TransferCard shape core/EventCatalog.py's Phase2CardMovement case builds
        for a BENCH -> ACTIVE_CARD move: the incoming bench card swaps in, the outgoing active
        card swaps out to bench (carrying its own retreat_cost as that leg's cost - see
        TransferCard's own cost field and A2's retreat-cost fix), both tagged PLAYER_CHOICE in
        one packet.'''
        bench_deck = self.player.card_piles[DeckType.BENCH]
        active_deck = self.player.card_piles[DeckType.ACTIVE_CARD]
        _id = AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)
        return Packet(_id, [
            TransferCard(_id, self.incoming, bench_deck, active_deck, self.env),
            TransferCard(_id, self.active, active_deck, bench_deck, self.env, self.active.retreat_cost),
        ])

    async def test_retreat_charges_the_outgoing_active_cards_own_cost(self):
        '''Legal retreat: the active card's own retreat_cost (1) is fully covered by its 1
        attached energy - must succeed and charge that energy, regardless of the incoming bench
        card's own (higher) retreat_cost. Against the old buggy check, this was wrongly rejected
        because 1 (active's energy) < 3 (incoming's retreat_cost).'''
        self.active.retreat_cost = 1
        self.active.energy_tokens = [EnergyToken("t1")]
        self.incoming.retreat_cost = 3

        self.env.push_packet(self._retreat_packet())
        await self.env.engine.flush(lambda: False)

        self.assertIs(self.player.card_piles[DeckType.ACTIVE_CARD].cards_holding[0], self.incoming)
        self.assertIn(self.active, self.player.card_piles[DeckType.BENCH].cards_holding)
        self.assertEqual(len(self.active.energy_tokens), 0)

    async def test_retreat_rejected_when_the_outgoing_active_card_cant_afford_its_own_cost(self):
        '''Illegal retreat: the active card's own retreat_cost (3) exceeds its 1 attached energy -
        must be rejected regardless of the incoming bench card's own (lower) retreat_cost.'''
        self.active.retreat_cost = 3
        self.active.energy_tokens = [EnergyToken("t1")]
        self.incoming.retreat_cost = 1

        self.env.push_packet(self._retreat_packet())
        await self.env.engine.flush(lambda: False)

        self.assertIs(self.player.card_piles[DeckType.ACTIVE_CARD].cards_holding[0], self.active)
        self.assertIn(self.incoming, self.player.card_piles[DeckType.BENCH].cards_holding)
        self.assertEqual(len(self.active.energy_tokens), 1)  # untouched - nothing was charged


if __name__ == "__main__":
    unittest.main()
