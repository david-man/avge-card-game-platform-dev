import unittest

from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment, EnergyToken
from ....avge_abstracts.AVGEDeck import DeckType
from ....constants import User, ActionTypes, ResponseStatus, AVGEPlayerAttribute
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....engine.event import Packet
from ....core.EventCatalog import TransferCard, AVGEEnergyTransfer
from ....testing.helpers import Dummy, TestIO, core_listeners, run_attack
from .BarronLee import BarronLee


class BarronLeeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        decks = {User.PLAYER_1: [BarronLee] * 5, User.PLAYER_2: [Dummy] * 5}
        self.env = AVGEEnvironment(TestIO(), decks, core_listeners())
        self.p1 = self.env.players[User.PLAYER_1]
        self.p2 = self.env.players[User.PLAYER_2]

        # Put each player's first deck card into play via the real TransferCard event,
        # so BarronLee.on_transfer fires and the engine's TransferCard special case
        # attaches the passive listener.
        for p in (self.p1, self.p2):
            card = p.card_piles[DeckType.DECK][0]
            _id = AVGEEngineID(None, ActionTypes.ENV, None)
            pkt = Packet(_id, [TransferCard(_id, card, p.card_piles[DeckType.DECK], p.card_piles[DeckType.ACTIVE_CARD], self.env)])
            self.env.push_packet(pkt)
            await self.env.engine.flush(lambda: False)

        self.active1 = self.env.get_player_active(self.p1)
        self.active2 = self.env.get_player_active(self.p2)
        assert isinstance(self.active1, BarronLee) and isinstance(self.active2, Dummy)

        # unrelated per-turn "energy add" limit defaults to 0; bump it so PLAYER_CHOICE
        # transfers below aren't blocked by that unrelated rule, isolating BarronLee's
        # own regulator.
        self.p1.attributes[AVGEPlayerAttribute.ENERGY_ADD_REMAINING_IN_TURN] = 5
        self.p2.attributes[AVGEPlayerAttribute.ENERGY_ADD_REMAINING_IN_TURN] = 5

    async def test_passive_attaches_on_entering_play(self):
        self.assertIsNotNone(self.active1._energy_cap_listener)

    async def test_cap_ignores_non_player_choice_overflow(self):
        self.active2.energy_tokens = [EnergyToken(f"t{i}") for i in range(3)]
        _id = AVGEEngineID(None, ActionTypes.ENV, None)
        pkt = Packet(_id, [AVGEEnergyTransfer(_id, self.env, self.active2, self.env)])
        pkt.set_engine(self.env.engine)
        res = await pkt.flush()
        self.assertEqual(res, ResponseStatus.SUCCESS)
        self.assertEqual(len(self.active2.energy_tokens), 3)

    async def test_cap_cancels_player_choice_overflow(self):
        self.active2.energy_tokens = [EnergyToken(f"t{i}") for i in range(3)]
        _id = AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)
        pkt = Packet(_id, [AVGEEnergyTransfer(_id, self.env, self.active2, self.env)])
        pkt.set_engine(self.env.engine)
        res = await pkt.flush()
        self.assertEqual(res, ResponseStatus.REGULATE_FAIL)
        self.assertEqual(len(self.active2.energy_tokens), 3)

    async def test_cap_does_not_block_own_side(self):
        self.active1.energy_tokens = [EnergyToken(f"s{i}") for i in range(3)]
        _id = AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)
        pkt = Packet(_id, [AVGEEnergyTransfer(_id, self.env, self.active1, self.env)])
        pkt.set_engine(self.env.engine)
        res = await pkt.flush()
        self.assertEqual(res, ResponseStatus.SUCCESS)
        self.assertEqual(len(self.active1.energy_tokens), 4)

    async def test_embouchure_deals_damage_and_reallocates_energy(self):
        hp_before = self.active2.hp
        await run_attack(self.env, self.active1, ActionTypes.ATK_1, energy=4)
        self.assertEqual(self.active2.hp, hp_before - 20)
        self.assertEqual(len(self.active1.energy_tokens), 4)  # all 4 tokens re-assigned back (only target offered)

    async def test_listener_cleaned_up_on_leaving_play(self):
        _id = AVGEEngineID(None, ActionTypes.ENV, None)
        pkt = Packet(_id, [TransferCard(_id, self.active1, self.p1.card_piles[DeckType.ACTIVE_CARD], self.p1.card_piles[DeckType.DISCARD], self.env)])
        self.env.push_packet(pkt)
        await self.env.engine.flush(lambda: False)
        self.assertIsNone(self.active1._energy_cap_listener)
        still_registered = any(isinstance(l, BarronLee._EnergyCapRegulator) for l in self.env.engine.listeners)
        self.assertFalse(still_registered)


if __name__ == "__main__":
    unittest.main()
