import unittest

from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ....avge_abstracts.AVGEDeck import DeckType
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....constants import User, ActionTypes
from ....engine.event import Packet
from ....core.EventCatalog import TransferCard
from ....testing.helpers import Dummy, TestIO, core_listeners, put_into_play, bench, run_attack, activate_ability
from .HappyRuthJara import HappyRuthJara


class HappyRuthJaraTests(unittest.IsolatedAsyncioTestCase):
    def _make_env(self, p1_deck, p2_deck):
        io = TestIO()
        env = AVGEEnvironment(io, {User.PLAYER_1: p1_deck, User.PLAYER_2: p2_deck}, core_listeners())
        env.turn = User.PLAYER_1
        return env, io

    async def test_coloratura_both_heads(self):
        env, io = self._make_env([HappyRuthJara], [Dummy])
        q1 = env.players[User.PLAYER_1]
        active1 = await put_into_play(env, q1)
        active2 = await put_into_play(env, env.players[User.PLAYER_2])

        io.coinflip_results = [1, 1]
        hp_before = active2.hp
        await run_attack(env, active1, ActionTypes.ATK_1, energy=3)
        self.assertEqual(hp_before - active2.hp, 70)  # 30 + 40 crit bonus

    async def test_coloratura_not_both_heads(self):
        env, io = self._make_env([HappyRuthJara], [Dummy])
        q1 = env.players[User.PLAYER_1]
        active1 = await put_into_play(env, q1)
        active2 = await put_into_play(env, env.players[User.PLAYER_2])

        io.coinflip_results = [1, 0]
        hp_before = active2.hp
        await run_attack(env, active1, ActionTypes.ATK_1, energy=3)
        self.assertEqual(hp_before - active2.hp, 30)

    async def test_can_play_blocked_right_after_hand_to_bench_this_turn(self):
        env, io = self._make_env([Dummy, HappyRuthJara], [Dummy])
        q1 = env.players[User.PLAYER_1]
        await put_into_play(env, q1)
        await put_into_play(env, env.players[User.PLAYER_2])

        # get her into hand directly (setup only, bypassing the engine), then do a *real*
        # HAND -> BENCH transfer, since can_play's history check specifically looks for that
        ruth = q1.card_piles[DeckType.DECK][0]
        deck = q1.card_piles[DeckType.DECK]
        hand = q1.card_piles[DeckType.HAND]
        deck.cards_holding.remove(ruth)
        hand.cards_holding.append(ruth)
        ruth.deck_type = DeckType.HAND
        _id = AVGEEngineID(None, ActionTypes.ENV, None)
        env.push_packet(Packet(_id, [TransferCard(_id, ruth, hand, q1.card_piles[DeckType.BENCH], env)]))
        await env.engine.flush(lambda: False)

        self.assertFalse(HappyRuthJara._LeaveRehearsalEarly().can_play(ruth))

    async def test_can_play_opens_up_next_turn_and_ability_retreats_her(self):
        env, io = self._make_env([Dummy, HappyRuthJara], [Dummy])
        q1 = env.players[User.PLAYER_1]
        await put_into_play(env, q1)
        ruth = await bench(env, q1)
        await put_into_play(env, env.players[User.PLAYER_2])

        env.engine.history.new_chapter()
        self.assertTrue(HappyRuthJara._LeaveRehearsalEarly().can_play(ruth))

        await activate_ability(env, ruth)
        self.assertEqual(ruth.deck_type, DeckType.HAND)

    async def test_can_play_blocked_on_opponents_turn(self):
        env, io = self._make_env([Dummy, HappyRuthJara], [Dummy])
        q1 = env.players[User.PLAYER_1]
        await put_into_play(env, q1)
        ruth = await bench(env, q1)
        await put_into_play(env, env.players[User.PLAYER_2])

        env.engine.history.new_chapter()  # get past "just benched this turn"
        env.turn = User.PLAYER_2
        self.assertFalse(HappyRuthJara._LeaveRehearsalEarly().can_play(ruth))

    async def test_can_play_blocked_while_active(self):
        env, io = self._make_env([HappyRuthJara], [Dummy])
        q1 = env.players[User.PLAYER_1]
        active1 = await put_into_play(env, q1)
        await put_into_play(env, env.players[User.PLAYER_2])

        env.engine.history.new_chapter()
        self.assertFalse(HappyRuthJara._LeaveRehearsalEarly().can_play(active1))

    async def test_engine_gate_blocks_illegal_activation_end_to_end(self):
        # Full end-to-end (not just can_play() in isolation): attempt ACTIVATE_ABILITY on
        # the very turn she was benched from hand. AVGEPlayCharacterCardValidityCheck
        # should REGULATE_FAIL the whole event before HappyRuthJara's own __call__ ever
        # runs - she should stay on the bench.
        env, io = self._make_env([Dummy, HappyRuthJara], [Dummy])
        q1 = env.players[User.PLAYER_1]
        await put_into_play(env, q1)

        ruth = q1.card_piles[DeckType.DECK][0]
        deck = q1.card_piles[DeckType.DECK]
        hand = q1.card_piles[DeckType.HAND]
        deck.cards_holding.remove(ruth)
        hand.cards_holding.append(ruth)
        ruth.deck_type = DeckType.HAND
        _id = AVGEEngineID(None, ActionTypes.ENV, None)
        env.push_packet(Packet(_id, [TransferCard(_id, ruth, hand, q1.card_piles[DeckType.BENCH], env)]))
        await env.engine.flush(lambda: False)
        await put_into_play(env, env.players[User.PLAYER_2])

        self.assertFalse(HappyRuthJara._LeaveRehearsalEarly().can_play(ruth))
        await activate_ability(env, ruth)
        self.assertEqual(ruth.deck_type, DeckType.BENCH)  # unchanged

    async def test_can_play_blocked_with_tool_attached(self):
        env, io = self._make_env([Dummy, HappyRuthJara], [Dummy])
        q1 = env.players[User.PLAYER_1]
        await put_into_play(env, q1)
        ruth = await bench(env, q1)
        await put_into_play(env, env.players[User.PLAYER_2])
        env.engine.history.new_chapter()

        self.assertTrue(HappyRuthJara._LeaveRehearsalEarly().can_play(ruth))

        # Fake-attach a tool by dropping a placeholder object straight into cards_holding -
        # only len(tools_attached) > 0 matters here, not a fully playable tool card.
        ruth.tools_attached.cards_holding.append(object())
        self.assertFalse(HappyRuthJara._LeaveRehearsalEarly().can_play(ruth))


if __name__ == "__main__":
    unittest.main()
