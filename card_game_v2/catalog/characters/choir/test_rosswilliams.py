import unittest

from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment, EnergyToken
from ....avge_abstracts.AVGEDeck import DeckType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....constants import User, ActionTypes, AVGEPlayerAttribute
from ....engine.event import Packet
from ....core.EventCatalog import AtkPhase, TransferCard
from ....testing.helpers import Dummy, TestIO, core_listeners, put_into_play, bench, discard, run_attack
from .RossWilliams import RossWilliams


async def fire_atk_phase(env):
    _id = AVGEEngineID(None, ActionTypes.ENV, None)
    env.push_packet(Packet(_id, [AtkPhase(_id, env)]))
    await env.engine.flush(lambda: False)


class RossWilliamsTests(unittest.IsolatedAsyncioTestCase):
    def _make_env(self, p1_deck, p2_deck):
        io = TestIO()
        env = AVGEEnvironment(io, {User.PLAYER_1: p1_deck, User.PLAYER_2: p2_deck}, core_listeners())
        env.turn = User.PLAYER_1
        return env, io

    # --- Ross Attack! (the ATK_1 itself, run while Ross is active - no hijack involved) ---

    async def test_ross_attack_does_nothing_if_neither_side_has_a_benched_ross(self):
        env, io = self._make_env([RossWilliams, Dummy], [Dummy, RossWilliams])
        p1 = env.players[User.PLAYER_1]
        p2 = env.players[User.PLAYER_2]
        active1 = await put_into_play(env, p1)
        active2 = await put_into_play(env, p2)
        self.assertIsInstance(active1, RossWilliams)

        hp_before = active2.hp
        await run_attack(env, active1, ActionTypes.ATK_1, energy=2)
        self.assertEqual(active2.hp, hp_before)

    async def test_ross_attack_deals_damage_if_opponent_has_a_benched_ross(self):
        env, io = self._make_env([RossWilliams, Dummy], [Dummy, RossWilliams])
        p1 = env.players[User.PLAYER_1]
        p2 = env.players[User.PLAYER_2]
        active1 = await put_into_play(env, p1)
        active2 = await put_into_play(env, p2)
        opp_ross = await bench(env, p2)
        self.assertIsInstance(opp_ross, RossWilliams)

        io.card_answer_index = 0  # opponent's active is allowed_selections[0]
        hp_before = active2.hp
        await run_attack(env, active1, ActionTypes.ATK_1, energy=2)
        self.assertEqual(hp_before - active2.hp, 20)

    # --- I Am Become Ross (the passive hijack) ---

    async def test_energy_boundary_for_offering_the_hijack(self):
        for energy, expect_offer in [(1, False), (2, True), (3, True)]:
            env, io = self._make_env([Dummy, RossWilliams], [Dummy])
            q1 = env.players[User.PLAYER_1]
            dummy_active = await put_into_play(env, q1)
            await bench(env, q1)
            await put_into_play(env, env.players[User.PLAYER_2])

            q1.attributes[AVGEPlayerAttribute.ATTACKS_LEFT] = 1
            dummy_active.energy_tokens = [EnergyToken(f"e{i}") for i in range(energy)]
            io.string_answer = "No"  # decline either way; only whether it was asked matters
            await fire_atk_phase(env)
            self.assertEqual(io.string_query_count > 0, expect_offer, f"energy={energy}")

    async def test_ross_active_never_offers_his_own_hijack(self):
        env, io = self._make_env([RossWilliams, Dummy], [Dummy])
        q1 = env.players[User.PLAYER_1]
        ross_active = await put_into_play(env, q1)  # Ross is the active character himself
        await put_into_play(env, env.players[User.PLAYER_2])
        self.assertIsNotNone(ross_active._hijack_regulator)  # attached regardless of active/bench

        q1.attributes[AVGEPlayerAttribute.ATTACKS_LEFT] = 1
        ross_active.energy_tokens = [EnergyToken("e0"), EnergyToken("e1"), EnergyToken("e2")]
        io.string_answer = "No"
        await fire_atk_phase(env)
        self.assertEqual(io.string_query_count, 0)

    async def test_two_ross_on_the_same_side_each_get_a_chance(self):
        env, io = self._make_env([Dummy, RossWilliams, RossWilliams], [Dummy])
        q1 = env.players[User.PLAYER_1]
        dummy_active = await put_into_play(env, q1)
        ross1 = await bench(env, q1)
        ross2 = await bench(env, q1)
        await put_into_play(env, env.players[User.PLAYER_2])
        self.assertIsNotNone(ross1._hijack_regulator)
        self.assertIsNotNone(ross2._hijack_regulator)

        q1.attributes[AVGEPlayerAttribute.ATTACKS_LEFT] = 1
        dummy_active.energy_tokens = [EnergyToken("e0"), EnergyToken("e1")]
        io.string_answers = ["No", "Yes"]
        await fire_atk_phase(env)
        self.assertEqual(io.string_query_count, 2)
        self.assertEqual(q1.attributes[AVGEPlayerAttribute.ATTACKS_LEFT], 0)

    async def test_ross_on_both_sides_references_correct_owner_in_each_prompt(self):
        env, io = self._make_env([Dummy, RossWilliams], [Dummy, RossWilliams])
        q1 = env.players[User.PLAYER_1]
        q2 = env.players[User.PLAYER_2]
        dummy_active = await put_into_play(env, q1)
        await bench(env, q1)
        await put_into_play(env, q2)
        await bench(env, q2)

        q1.attributes[AVGEPlayerAttribute.ATTACKS_LEFT] = 1
        dummy_active.energy_tokens = [EnergyToken("e0"), EnergyToken("e1")]

        seen_messages = []
        orig_send = io.send

        async def spying_send(user, io_obj):
            if hasattr(io_obj, "header_msg"):
                seen_messages.append(io_obj.header_msg)
            await orig_send(user, io_obj)
        io.send = spying_send

        io.string_answers = ["No", "No"]
        await fire_atk_phase(env)
        self.assertTrue(any("PLAYER_1" in m for m in seen_messages))
        self.assertTrue(any("PLAYER_2" in m for m in seen_messages))

    async def test_cleanup_on_discard_stops_future_offers(self):
        env, io = self._make_env([Dummy, RossWilliams], [Dummy])
        q1 = env.players[User.PLAYER_1]
        dummy_active = await put_into_play(env, q1)
        ross_bench = await bench(env, q1)
        await put_into_play(env, env.players[User.PLAYER_2])
        self.assertIsNotNone(ross_bench._hijack_regulator)
        listeners_before = len(env.engine.listeners)

        _id = AVGEEngineID(None, ActionTypes.ENV, None)
        env.push_packet(Packet(_id, [TransferCard(_id, ross_bench, q1.card_piles[DeckType.BENCH], q1.card_piles[DeckType.DISCARD], env)]))
        await env.engine.flush(lambda: False)
        self.assertIsNone(ross_bench._hijack_regulator)
        self.assertEqual(len(env.engine.listeners), listeners_before - 1)

        q1.attributes[AVGEPlayerAttribute.ATTACKS_LEFT] = 1
        dummy_active.energy_tokens = [EnergyToken("e0"), EnergyToken("e1")]
        io.string_answer = "No"
        await fire_atk_phase(env)
        self.assertEqual(io.string_query_count, 0)

    async def test_multiple_attacks_left_loops_back_instead_of_ending_turn_early(self):
        env, io = self._make_env([Dummy, RossWilliams], [Dummy])
        q1 = env.players[User.PLAYER_1]
        dummy_active = await put_into_play(env, q1)
        await bench(env, q1)
        await put_into_play(env, env.players[User.PLAYER_2])

        q1.attributes[AVGEPlayerAttribute.ATTACKS_LEFT] = 2
        dummy_active.energy_tokens = [EnergyToken("e0"), EnergyToken("e1")]
        io.string_answer = "Yes"
        self.assertEqual(env.turn, User.PLAYER_1)
        await fire_atk_phase(env)
        # After the hijack: ATTACKS_LEFT 2->1, _attack_switch pushes another AtkPhase (since
        # !=0), which TestIO answers with SKIP, decrementing to 0, which then correctly ends
        # the turn - exactly once, not zero or two times.
        self.assertEqual(env.turn, User.PLAYER_2)
        self.assertEqual(q1.attributes[AVGEPlayerAttribute.ATTACKS_LEFT], 0)

    async def test_hijack_cost_zero_bypasses_energy_check_and_still_consumes_the_turn(self):
        env, io = self._make_env([Dummy, RossWilliams], [Dummy])
        q1 = env.players[User.PLAYER_1]
        dummy_active = await put_into_play(env, q1)
        ross_bench = await bench(env, q1)
        await put_into_play(env, env.players[User.PLAYER_2])

        q1.attributes[AVGEPlayerAttribute.ATTACKS_LEFT] = 1
        dummy_active.energy_tokens = [EnergyToken("e0"), EnergyToken("e1")]
        ross_bench.energy_tokens = []  # deliberately empty, to prove cost=0 bypasses the check
        io.string_answer = "Yes"
        await fire_atk_phase(env)
        # dummy_active has no benched Ross of its own and the opponent doesn't either on this
        # board, so Ross's atk_1 falls through to "did nothing" - what matters is that it ran
        # at all (no cost-check failure) and consumed the turn's attack.
        self.assertEqual(q1.attributes[AVGEPlayerAttribute.ATTACKS_LEFT], 0)

    async def test_declined_hijack_falls_through_to_normal_skip(self):
        env, io = self._make_env([Dummy, RossWilliams], [Dummy])
        q1 = env.players[User.PLAYER_1]
        dummy_active = await put_into_play(env, q1)
        await bench(env, q1)
        await put_into_play(env, env.players[User.PLAYER_2])

        q1.attributes[AVGEPlayerAttribute.ATTACKS_LEFT] = 1
        dummy_active.energy_tokens = [EnergyToken("e0"), EnergyToken("e1")]
        io.string_answer = "No"
        await fire_atk_phase(env)
        self.assertEqual(q1.attributes[AVGEPlayerAttribute.ATTACKS_LEFT], 0)

    async def test_hijack_player_has_branch_retrieves_a_real_discarded_card(self):
        env, io = self._make_env([Dummy, RossWilliams, Dummy], [Dummy])
        q1 = env.players[User.PLAYER_1]
        dummy_active = await put_into_play(env, q1)
        await bench(env, q1)
        discarded_card = await discard(env, q1)
        await put_into_play(env, env.players[User.PLAYER_2])

        hand_before = len(q1.card_piles[DeckType.HAND])
        q1.attributes[AVGEPlayerAttribute.ATTACKS_LEFT] = 1
        dummy_active.energy_tokens = [EnergyToken("e0"), EnergyToken("e1")]
        io.string_answer = "Yes"
        io.card_answer_index = 0
        await fire_atk_phase(env)
        self.assertEqual(discarded_card.deck_type, DeckType.HAND)
        self.assertEqual(len(q1.card_piles[DeckType.HAND]), hand_before + 1)

    async def test_hijack_opp_has_branch_can_target_a_benched_opponent(self):
        # P2's Ross is benched (opp_has=True from P1's perspective); P1 has no Ross of its own.
        env, io = self._make_env([Dummy], [Dummy, RossWilliams, Dummy])
        q1 = env.players[User.PLAYER_1]
        q2 = env.players[User.PLAYER_2]
        dummy_active = await put_into_play(env, q1)
        opp_active = await put_into_play(env, q2)
        opp_ross = await bench(env, q2)
        opp_bench2 = await bench(env, q2)

        q1.attributes[AVGEPlayerAttribute.ATTACKS_LEFT] = 1
        dummy_active.energy_tokens = [EnergyToken("e0"), EnergyToken("e1")]
        io.string_answer = "Yes"
        # allowed_selections for the target query = opponent's [ACTIVE_CARD, *BENCH]
        targets_order = [opp_active, opp_ross, opp_bench2]
        io.card_answer_index = targets_order.index(opp_bench2)

        hp_before = opp_bench2.hp
        await fire_atk_phase(env)
        self.assertEqual(hp_before - opp_bench2.hp, 20)
        self.assertEqual(opp_active.hp, opp_active.max_hp)

    async def test_cross_player_hijack_deals_real_damage(self):
        # player_has=False, opp_has=True from the *acting* player's perspective, since the
        # hijacking Ross belongs to the opponent - the only way to reach the damage branch
        # via a hijack (your own benched Ross always makes player_has=True for yourself).
        env, io = self._make_env([Dummy], [Dummy, RossWilliams])
        q1 = env.players[User.PLAYER_1]
        q2 = env.players[User.PLAYER_2]
        dummy_active = await put_into_play(env, q1)  # no Ross on P1's side at all
        opp_active = await put_into_play(env, q2)
        await bench(env, q2)  # P2's benched Ross offers to hijack P1's turn

        q1.attributes[AVGEPlayerAttribute.ATTACKS_LEFT] = 1
        dummy_active.energy_tokens = [EnergyToken("e0"), EnergyToken("e1")]
        io.string_answer = "Yes"
        io.card_answer_index = 0  # opponent's active is allowed_selections[0]

        hp_before = opp_active.hp
        await fire_atk_phase(env)
        self.assertEqual(hp_before - opp_active.hp, 20)


if __name__ == "__main__":
    unittest.main()
