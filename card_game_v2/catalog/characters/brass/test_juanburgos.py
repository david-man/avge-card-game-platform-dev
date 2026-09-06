import unittest

from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ....avge_abstracts.AVGEDeck import DeckType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....constants import User, ActionTypes
from ....engine.event import Packet
from ....core.EventCatalog import TransferCard
from ....testing.helpers import Dummy, TestIO, core_listeners, put_into_play, bench, run_attack
from .JuanBurgos import JuanBurgos
from .BarronLee import BarronLee


class JuanBurgosTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        decks = {User.PLAYER_1: [BarronLee, JuanBurgos, JuanBurgos], User.PLAYER_2: [Dummy] * 3}
        self.env = AVGEEnvironment(TestIO(), decks, core_listeners())
        self.env.turn = User.PLAYER_1

        self.p1 = self.env.players[User.PLAYER_1]
        self.p2 = self.env.players[User.PLAYER_2]

        self.active1 = await put_into_play(self.env, self.p1)  # BarronLee
        self.active2 = await put_into_play(self.env, self.p2)
        self.juan = await bench(self.env, self.p1)  # first JuanBurgos in deck
        assert isinstance(self.active1, BarronLee) and isinstance(self.juan, JuanBurgos) and isinstance(self.active2, Dummy)

    async def test_boost_attaches_while_benched(self):
        self.assertIsNotNone(self.juan._bench_boost)

    async def test_bench_boost_and_own_scaling_stack_across_two_juans(self):
        # Barron (Brass) attacks while the first Juan is benched -> +10 damage.
        hp_before = self.active2.hp
        await run_attack(self.env, self.active1, ActionTypes.ATK_1)
        self.assertEqual(hp_before - self.active2.hp, 30)  # 20 base + 10 buff

        # Bring in a second Juan to the bench, then swap Barron<->first Juan (active<->bench).
        juan2 = self.p1.card_piles[DeckType.DECK][0]
        eid = AVGEEngineID(None, ActionTypes.ENV, None)
        self.env.push_packet(Packet(eid, [TransferCard(eid, juan2, self.p1.card_piles[DeckType.DECK], self.p1.card_piles[DeckType.BENCH], self.env)]))
        await self.env.engine.flush(lambda: False)
        self.assertIsInstance(juan2, JuanBurgos)

        eid2 = AVGEEngineID(None, ActionTypes.ENV, None)
        self.env.push_packet(Packet(eid2, [
            TransferCard(eid2, self.active1, self.p1.card_piles[DeckType.ACTIVE_CARD], self.p1.card_piles[DeckType.BENCH], self.env),
            TransferCard(eid2, self.juan, self.p1.card_piles[DeckType.BENCH], self.p1.card_piles[DeckType.ACTIVE_CARD], self.env),
        ]))
        await self.env.engine.flush(lambda: False)
        self.assertIs(self.env.get_player_active(self.p1), self.juan)

        # Now Juan is active (attacking); bench holds Barron (brass) + juan2 (brass) = 2 brass
        # for Concert Pitch's own scaling, and juan2 (also benched+brass+friendly) independently
        # contributes its own Baking Buff +10 on top.
        hp_before = self.active2.hp
        await run_attack(self.env, self.juan, ActionTypes.ATK_1)
        self.assertEqual(hp_before - self.active2.hp, 80)  # 30 + 20*2 + 10

        # A bench<->active swap stays "in play" the whole time, so both listeners are
        # correctly left attached (they just go dynamically inert per their own deck_type
        # check while active, per match()).
        self.assertIsNotNone(self.juan._bench_boost)
        self.assertIsNotNone(juan2._bench_boost)


if __name__ == "__main__":
    unittest.main()
