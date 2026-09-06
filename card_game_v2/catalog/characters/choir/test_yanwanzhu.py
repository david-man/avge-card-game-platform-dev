import unittest

from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment, EnergyToken
from ....avge_abstracts.AVGEDeck import DeckType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....constants import User, ActionTypes
from ....engine.event import Packet
from ....core.EventCatalog import PhasePickCard, TransferCard
from ....testing.helpers import Dummy, TestIO, core_listeners, put_into_play, bench, run_attack
from .YanwanZhu import YanwanZhu


async def fire_phase_pick_card(env):
    _id = AVGEEngineID(None, ActionTypes.ENV, None)
    env.push_packet(Packet(_id, [PhasePickCard(_id, env)]))
    await env.engine.flush(lambda: False)


class YanwanZhuTests(unittest.IsolatedAsyncioTestCase):
    def _make_env(self, p1_deck, p2_deck):
        # Decks are sized to exactly what setup consumes, so both are empty by the time
        # any PhasePickCard fires - otherwise firing one directly cascades through the
        # real draw/Phase2/AtkPhase/TurnEnd machinery (TestIO auto-answers
        # Phase2Finish/SKIP), eventually flipping turn back and firing a *second*,
        # unintended PhasePickCard that would confound these isolated reactor checks.
        io = TestIO()
        env = AVGEEnvironment(io, {User.PLAYER_1: p1_deck, User.PLAYER_2: p2_deck}, core_listeners())
        env.turn = User.PLAYER_1
        return env, io

    async def test_energy_boundary_exactly_two(self):
        for energy, expect_heal in [(1, False), (2, True), (3, False)]:
            env, io = self._make_env([YanwanZhu, Dummy], [Dummy, Dummy])
            p1 = env.players[User.PLAYER_1]
            active1 = await put_into_play(env, p1)
            await put_into_play(env, env.players[User.PLAYER_2])
            hurt_ally = await bench(env, p1)
            hurt_ally.hp = 10

            active1.energy_tokens = [EnergyToken(f"e{i}") for i in range(energy)]
            await fire_phase_pick_card(env)
            healed = hurt_ally.hp != 10
            self.assertEqual(healed, expect_heal, f"energy={energy}")

    async def test_player_may_decline_the_heal(self):
        env, io = self._make_env([YanwanZhu, Dummy], [Dummy, Dummy])
        p1 = env.players[User.PLAYER_1]
        active1 = await put_into_play(env, p1)
        await put_into_play(env, env.players[User.PLAYER_2])
        hurt_ally = await bench(env, p1)
        hurt_ally.hp = 10

        active1.energy_tokens = [EnergyToken("e0"), EnergyToken("e1")]
        io.select_none = True
        await fire_phase_pick_card(env)
        self.assertEqual(hurt_ally.hp, 10)

    async def test_no_damaged_teammates_does_not_match_or_crash(self):
        env, io = self._make_env([YanwanZhu, Dummy], [Dummy, Dummy])
        p1 = env.players[User.PLAYER_1]
        active1 = await put_into_play(env, p1)
        await put_into_play(env, env.players[User.PLAYER_2])
        hurt_ally = await bench(env, p1)
        hurt_ally.hp = hurt_ally.max_hp

        active1.energy_tokens = [EnergyToken("e0"), EnergyToken("e1")]
        await fire_phase_pick_card(env)  # should just do nothing, not raise

    async def test_does_not_trigger_on_opponents_turn(self):
        # P2's deck must be fully drained too here (unlike the other tests, which never
        # flip env.turn to P2): PhasePickCard.act() looks at get_current_player()'s deck,
        # and a non-empty one cascades into a real draw/Phase2/TurnEnd chain that would
        # flip the turn straight back and confound this check.
        env, io = self._make_env([YanwanZhu, Dummy], [Dummy])
        p1 = env.players[User.PLAYER_1]
        active1 = await put_into_play(env, p1)
        await put_into_play(env, env.players[User.PLAYER_2])
        hurt_ally = await bench(env, p1)
        hurt_ally.hp = 10

        active1.energy_tokens = [EnergyToken("e0"), EnergyToken("e1")]
        env.turn = User.PLAYER_2
        await fire_phase_pick_card(env)
        self.assertEqual(hurt_ally.hp, 10)

    async def test_chooses_specific_candidate_among_several(self):
        env, io = self._make_env([YanwanZhu, Dummy, Dummy], [Dummy])
        p1 = env.players[User.PLAYER_1]
        active1 = await put_into_play(env, p1)
        await put_into_play(env, env.players[User.PLAYER_2])
        hurt_a = await bench(env, p1)
        hurt_b = await bench(env, p1)
        hurt_a.hp = 10
        hurt_b.hp = 20

        active1.energy_tokens = [EnergyToken("e0"), EnergyToken("e1")]
        candidates = active1._heal_reactor._candidates()
        io.card_answer_index = candidates.index(hurt_b)

        await fire_phase_pick_card(env)
        self.assertEqual(hurt_a.hp, 10)
        self.assertEqual(hurt_b.hp, 50)

    async def test_heal_does_not_overheal_past_max(self):
        env, io = self._make_env([YanwanZhu, Dummy], [Dummy])
        p1 = env.players[User.PLAYER_1]
        active1 = await put_into_play(env, p1)
        await put_into_play(env, env.players[User.PLAYER_2])
        hurt_ally = await bench(env, p1)
        hurt_ally.hp = hurt_ally.max_hp - 10  # only 10 below max, healing 30 should cap

        active1.energy_tokens = [EnergyToken("e0"), EnergyToken("e1")]
        await fire_phase_pick_card(env)
        self.assertEqual(hurt_ally.hp, hurt_ally.max_hp)

    async def test_cleanup_on_discard_stops_future_heals(self):
        env, io = self._make_env([YanwanZhu, Dummy], [Dummy])
        p1 = env.players[User.PLAYER_1]
        active1 = await put_into_play(env, p1)
        await put_into_play(env, env.players[User.PLAYER_2])
        await bench(env, p1)
        self.assertIsNotNone(active1._heal_reactor)
        listeners_before = len(env.engine.listeners)

        _id = AVGEEngineID(None, ActionTypes.ENV, None)
        env.push_packet(Packet(_id, [TransferCard(_id, active1, p1.card_piles[DeckType.ACTIVE_CARD], p1.card_piles[DeckType.DISCARD], env)]))
        await env.engine.flush(lambda: False)
        self.assertIsNone(active1._heal_reactor)
        self.assertEqual(len(env.engine.listeners), listeners_before - 1)

    async def test_intense_voice_hits_active_and_splashes_bench(self):
        env, io = self._make_env([YanwanZhu], [Dummy, Dummy])
        p2 = env.players[User.PLAYER_2]
        active1 = await put_into_play(env, env.players[User.PLAYER_1])
        active2 = await put_into_play(env, p2)
        bench_target = await bench(env, p2)

        hp_active_before = active2.hp
        hp_bench_before = bench_target.hp
        await run_attack(env, active1, ActionTypes.ATK_1, energy=3)
        self.assertEqual(hp_active_before - active2.hp, 60)
        self.assertEqual(hp_bench_before - bench_target.hp, 10)


if __name__ == "__main__":
    unittest.main()
