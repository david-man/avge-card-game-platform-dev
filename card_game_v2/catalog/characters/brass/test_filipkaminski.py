import unittest

from ....avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ....avge_abstracts.AVGEDeck import DeckType
from ....constants import User, ActionTypes
from ....avge_abstracts.AVGEID import AVGEEngineID
from ....engine.event import Packet
from ....core.EventCatalog import TransferCard
from ....testing.helpers import Dummy, DummyStadium, TestIO, core_listeners, put_into_play, run_attack
from .FilipKaminski import FilipKaminski


class FilipKaminskiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        decks = {User.PLAYER_1: [FilipKaminski] * 5, User.PLAYER_2: [Dummy] * 3}
        self.io = TestIO()
        self.env = AVGEEnvironment(self.io, decks, core_listeners())
        self.env.turn = User.PLAYER_1

        self.p1 = self.env.players[User.PLAYER_1]
        self.p2 = self.env.players[User.PLAYER_2]

        self.active1 = await put_into_play(self.env, self.p1)
        self.active2 = await put_into_play(self.env, self.p2)
        assert isinstance(self.active1, FilipKaminski) and isinstance(self.active2, Dummy)

    async def _drain_deck(self, player):
        while len(player.card_piles[DeckType.DECK]) > 0:
            top = player.card_piles[DeckType.DECK][0]
            _id = AVGEEngineID(None, ActionTypes.ENV, None)
            self.env.push_packet(Packet(_id, [TransferCard(_id, top, player.card_piles[DeckType.DECK], player.card_piles[DeckType.DISCARD], self.env)]))
            await self.env.engine.flush(lambda: False)

    async def test_heart_of_the_cards_correct_guess_hits(self):
        # P1's whole deck is FilipKaminski, so this guess always matches the drawn card.
        self.io.string_answer = "FilipKaminski"
        hp_before = self.active2.hp
        await run_attack(self.env, self.active1, ActionTypes.ATK_1)
        self.assertEqual(hp_before - self.active2.hp, 50)
        self.assertEqual(len(self.p1.card_piles[DeckType.HAND]), 1)

    async def test_heart_of_the_cards_wrong_guess_still_draws_no_damage(self):
        self.io.string_answer = "Dummy"  # not a card type in Filip's own piles
        hand_before = len(self.p1.card_piles[DeckType.HAND])
        hp_before = self.active2.hp
        await run_attack(self.env, self.active1, ActionTypes.ATK_1)
        self.assertEqual(hp_before - self.active2.hp, 0)
        self.assertEqual(len(self.p1.card_piles[DeckType.HAND]), hand_before + 1)

    async def test_heart_of_the_cards_empty_deck_does_nothing(self):
        await self._drain_deck(self.p1)
        hp_before = self.active2.hp
        await run_attack(self.env, self.active1, ActionTypes.ATK_1)
        self.assertEqual(hp_before - self.active2.hp, 0)

    async def test_intense_echo_no_stadium_hits_active_only(self):
        hp_before = self.active2.hp
        await run_attack(self.env, self.active1, ActionTypes.ATK_2)
        self.assertEqual(hp_before - self.active2.hp, 50)

    async def test_intense_echo_with_own_stadium_splashes_bench(self):
        stadium = DummyStadium("stadium_0", self.env, User.PLAYER_1, DeckType.HAND)
        self.env.stadium_cardholder.cards_holding.append(stadium)
        bench_card = Dummy("bench_0", self.env, User.PLAYER_2, DeckType.BENCH)
        self.p2.card_piles[DeckType.BENCH].cards_holding.append(bench_card)

        hp_before_active = self.active2.hp
        hp_before_bench = bench_card.hp
        await run_attack(self.env, self.active1, ActionTypes.ATK_2)
        self.assertEqual(hp_before_active - self.active2.hp, 50)
        self.assertEqual(hp_before_bench - bench_card.hp, 20)


if __name__ == "__main__":
    unittest.main()
