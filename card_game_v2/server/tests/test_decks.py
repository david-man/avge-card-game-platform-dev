import collections
import unittest

from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ...avge_abstracts.AVGEDeck import DeckType
from ...avge_abstracts.AVGECard import AVGECharacterCard
from ...constants import User
from ...testing.helpers import TestIO, core_listeners
from ..decks import build_preset_decks, CARDS_PER_DECK


class BuildPresetDecksTests(unittest.TestCase):
    def test_each_player_gets_the_right_number_of_cards(self):
        decks = build_preset_decks()
        self.assertEqual(len(decks[User.PLAYER_1]), CARDS_PER_DECK)
        self.assertEqual(len(decks[User.PLAYER_2]), CARDS_PER_DECK)

    def test_both_players_get_the_same_card_composition(self):
        decks = build_preset_decks()
        counts_p1 = collections.Counter(decks[User.PLAYER_1])
        counts_p2 = collections.Counter(decks[User.PLAYER_2])
        self.assertEqual(counts_p1, counts_p2)

    def test_all_entries_are_character_cards(self):
        decks = build_preset_decks()
        for card_cls in decks[User.PLAYER_1] + decks[User.PLAYER_2]:
            self.assertTrue(issubclass(card_cls, AVGECharacterCard))

    def test_deck_order_varies_across_calls(self):
        # Not a hard guarantee (random.sample could theoretically repeat an order), but with 20
        # cards drawn from a pool with real duplicates, an identical order across two independent
        # calls is astronomically unlikely - this catches an accidental "forgot to shuffle" bug.
        decks_a = build_preset_decks()
        decks_b = build_preset_decks()
        self.assertNotEqual(decks_a[User.PLAYER_1], decks_b[User.PLAYER_1])

    def test_builds_a_real_playable_environment(self):
        decks = build_preset_decks()
        env = AVGEEnvironment(TestIO(), decks, core_listeners())
        p1 = env.players[User.PLAYER_1]
        p2 = env.players[User.PLAYER_2]
        self.assertEqual(len(p1.card_piles[DeckType.DECK]), CARDS_PER_DECK)
        self.assertEqual(len(p2.card_piles[DeckType.DECK]), CARDS_PER_DECK)


if __name__ == "__main__":
    unittest.main()
