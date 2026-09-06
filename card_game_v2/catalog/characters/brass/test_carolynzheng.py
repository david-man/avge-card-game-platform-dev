import unittest

from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ....avge_abstracts.AVGEDeck import DeckType
from ....constants import User, ActionTypes
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....engine.event import Packet
from ....core.EventCatalog import TransferCard
from ....testing.helpers import Dummy, TestIO, core_listeners, put_into_play, run_attack
from .CarolynZheng import CarolynZheng


def advance_chapter(env):
    # Directly simulate "a turn boundary passed" without driving the full Phase2/AtkPhase
    # state machine (which needs a much more complete fake IO layer than this cares about).
    env.engine.history.new_chapter()
    env.turn = env.turn.next


class CarolynZhengTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        decks = {User.PLAYER_1: [CarolynZheng] * 5, User.PLAYER_2: [Dummy] * 5}
        self.env = AVGEEnvironment(TestIO(), decks, core_listeners())
        self.env.turn = User.PLAYER_1  # deterministic

        self.p1 = self.env.players[User.PLAYER_1]
        self.p2 = self.env.players[User.PLAYER_2]

        self.active1 = await put_into_play(self.env, self.p1)
        self.active2 = await put_into_play(self.env, self.p2)
        assert isinstance(self.active1, CarolynZheng) and isinstance(self.active2, Dummy)

    async def test_passive_attaches_on_entering_play(self):
        self.assertIsNotNone(self.active1._attack_modifier)

    async def test_buff_tracks_whether_she_attacked_last_turn(self):
        # Turn 1 (her very first turn): no prior turn exists -> buffed attack (100 dmg)
        hp_before = self.active2.hp
        await run_attack(self.env, self.active1, ActionTypes.ATK_1, energy=3)
        self.assertEqual(hp_before - self.active2.hp, 100)

        advance_chapter(self.env)  # P1 -> P2
        advance_chapter(self.env)  # P2 -> P1 (her second turn; increment=2 is now her turn 1)

        # Turn 2: she DID attack last turn -> no buff (70 dmg)
        self.active2.hp = self.active2.max_hp
        hp_before = self.active2.hp
        await run_attack(self.env, self.active1, ActionTypes.ATK_1, energy=3)
        self.assertEqual(hp_before - self.active2.hp, 70)

        # Turn 3: she skips her attack entirely (no run_attack call)
        advance_chapter(self.env)  # P1 -> P2
        advance_chapter(self.env)  # P2 -> P1 (her third turn begins)

        # Turn 4: she did NOT attack on turn 3 -> buffed again (100 dmg)
        advance_chapter(self.env)  # P1 -> P2
        advance_chapter(self.env)  # P2 -> P1 (her fourth turn begins)
        self.active2.hp = self.active2.max_hp
        hp_before = self.active2.hp
        await run_attack(self.env, self.active1, ActionTypes.ATK_1, energy=3)
        self.assertEqual(hp_before - self.active2.hp, 100)

    async def test_listener_cleaned_up_on_leaving_play(self):
        _id = AVGEEngineID(None, ActionTypes.ENV, None)
        pkt = Packet(_id, [TransferCard(_id, self.active1, self.p1.card_piles[DeckType.ACTIVE_CARD], self.p1.card_piles[DeckType.DISCARD], self.env)])
        self.env.push_packet(pkt)
        await self.env.engine.flush(lambda: False)
        self.assertIsNone(self.active1._attack_modifier)


if __name__ == "__main__":
    unittest.main()
