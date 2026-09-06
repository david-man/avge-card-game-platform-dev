import unittest

from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....constants import User, ActionTypes
from ....engine.event import Packet
from ....core.EventCatalog import PlayCharacterCard
from ....testing.helpers import Dummy, TestIO, core_listeners, put_into_play, bench, run_attack
from .RyanDu import RyanDu


class RyanDuTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        decks = {User.PLAYER_1: [RyanDu, Dummy, Dummy, Dummy], User.PLAYER_2: [Dummy]}
        self.env = AVGEEnvironment(TestIO(), decks, core_listeners())
        self.env.turn = User.PLAYER_1

        self.p1 = self.env.players[User.PLAYER_1]
        self.p2 = self.env.players[User.PLAYER_2]

        self.active1 = await put_into_play(self.env, self.p1)
        self.active2 = await put_into_play(self.env, self.p2)
        assert isinstance(self.active1, RyanDu) and isinstance(self.active2, Dummy)

    async def test_zero_energy_blocked_by_cost_check(self):
        # ATK_1 costs 1 - with 0 energy the engine's own validity check should block it
        # entirely, before RyanDu's own __call__ ever runs.
        self.assertEqual(len(self.active1.energy_tokens), 0)
        hp_before = self.active2.hp
        _id = AVGEEngineID(None, ActionTypes.PLAYER_CHOICE, None)
        self.env.push_packet(Packet(_id, [PlayCharacterCard(_id, self.active1, ActionTypes.ATK_1, 1, self.env)]))
        await self.env.engine.flush(lambda: False)
        self.assertEqual(self.active2.hp, hp_before)

    async def test_tabemono_king_scales_with_energy_and_resets_it(self):
        for energy in (1, 3, 2, 4):
            self.active2.hp = self.active2.max_hp
            hp_before = self.active2.hp
            await run_attack(self.env, self.active1, ActionTypes.ATK_1, energy=energy)
            self.assertEqual(hp_before - self.active2.hp, 30 * energy)
            self.assertEqual(len(self.active1.energy_tokens), 0)

    async def test_chorus_with_empty_bench(self):
        hp_before = self.active2.hp
        await run_attack(self.env, self.active1, ActionTypes.ATK_2, energy=2)
        self.assertEqual(hp_before - self.active2.hp, 20)

    async def test_chorus_scales_with_growing_bench(self):
        expected_bench = 0
        for _ in range(3):
            await bench(self.env, self.p1)
            expected_bench += 1
            self.active2.hp = self.active2.max_hp
            hp_before = self.active2.hp
            await run_attack(self.env, self.active1, ActionTypes.ATK_2, energy=2)
            self.assertEqual(hp_before - self.active2.hp, 20 + 10 * expected_bench)


if __name__ == "__main__":
    unittest.main()
