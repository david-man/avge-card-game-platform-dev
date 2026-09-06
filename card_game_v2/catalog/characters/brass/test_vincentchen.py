import unittest

from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ....constants import User, ActionTypes
from ....testing.helpers import Dummy, TestIO, core_listeners, put_into_play, bench, run_attack
from .VincentChen import VincentChen


class VincentChenTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        decks = {User.PLAYER_1: [VincentChen, Dummy], User.PLAYER_2: [Dummy] * 3}
        self.env = AVGEEnvironment(TestIO(), decks, core_listeners())
        self.env.turn = User.PLAYER_1

        self.p1 = self.env.players[User.PLAYER_1]
        self.p2 = self.env.players[User.PLAYER_2]

        self.active1 = await put_into_play(self.env, self.p1)
        self.active2 = await put_into_play(self.env, self.p2)
        assert isinstance(self.active1, VincentChen) and isinstance(self.active2, Dummy)

    async def test_fanfare_deals_plain_damage(self):
        hp_before = self.active2.hp
        await run_attack(self.env, self.active1, ActionTypes.ATK_1)
        self.assertEqual(hp_before - self.active2.hp, 20)

    async def test_cherry_oil_with_no_bench_deals_damage_and_self_cleans(self):
        hp_before = self.active2.hp
        listeners_before = len(self.env.engine.listeners)
        await run_attack(self.env, self.active1, ActionTypes.ATK_2)
        self.assertEqual(hp_before - self.active2.hp, 40)
        self.assertEqual(len(self.env.engine.listeners), listeners_before)  # one-shot reactor cleaned itself up

    async def test_cherry_oil_with_bench_heals_chosen_ally(self):
        bench_card = await bench(self.env, self.p1)  # the Dummy in P1's deck
        bench_card.hp = 1  # near-dead, so the heal is clearly visible
        hp_before = self.active2.hp
        await run_attack(self.env, self.active1, ActionTypes.ATK_2)
        self.assertEqual(hp_before - self.active2.hp, 40)
        self.assertEqual(bench_card.hp, min(bench_card.max_hp, 1 + 40))


if __name__ == "__main__":
    unittest.main()
