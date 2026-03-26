from __future__ import annotations

import unittest

from card_game.abstract.card import Card
from card_game.avge_abstracts.envcache import EnvironmentCache


class EnvironmentCacheTests(unittest.TestCase):
    def _make_cards_and_cache(self):
        card_a = Card("card_a")
        card_b = Card("card_b")
        cache = EnvironmentCache([card_a.unique_id, card_b.unique_id])
        return card_a, card_b, cache

    def test_realtime_set_and_get_without_capture(self):
        card_a, _, cache = self._make_cards_and_cache()

        cache.set(card_a, "x", 10)
        self.assertEqual(cache.get(card_a, "x"), 10)

    def test_delete_missing_key_is_noop(self):
        card_a, _, cache = self._make_cards_and_cache()

        cache.delete(card_a, "missing")
        self.assertEqual(cache.get(card_a, "missing", "fallback"), "fallback")

    def test_capture_insert_then_rewind_removes_inserted_key(self):
        card_a, _, cache = self._make_cards_and_cache()

        cache.capture()
        cache.set(card_a, "inserted", 1)
        self.assertEqual(cache.get(card_a, "inserted"), 1)

        cache.rewind()
        self.assertEqual(cache.get(card_a, "inserted", None), None)

    def test_capture_alter_then_rewind_restores_old_value(self):
        card_a, _, cache = self._make_cards_and_cache()

        cache.set(card_a, "hp", 100)
        cache.capture()
        cache.set(card_a, "hp", 70)
        self.assertEqual(cache.get(card_a, "hp"), 70)

        cache.rewind()
        self.assertEqual(cache.get(card_a, "hp"), 100)

    def test_capture_delete_then_rewind_restores_deleted_value(self):
        card_a, _, cache = self._make_cards_and_cache()

        cache.set(card_a, "flag", True)
        cache.capture()
        cache.delete(card_a, "flag")
        self.assertEqual(cache.get(card_a, "flag", None), None)

        cache.rewind()
        self.assertEqual(cache.get(card_a, "flag"), True)

    def test_capture_mixed_operations_across_cards_rewind_consistent(self):
        card_a, card_b, cache = self._make_cards_and_cache()

        cache.set(card_a, "a", 1)
        cache.set(card_a, "b", 2)
        cache.set(card_b, "z", 9)

        cache.capture()
        cache.set(card_a, "a", 11)
        cache.delete(card_a, "b")
        cache.set(card_a, "c", 3)
        cache.set(card_b, "z", 99)
        cache.set(card_b, "new", "n")

        self.assertEqual(cache.get(card_a, "a"), 11)
        self.assertEqual(cache.get(card_a, "b", None), None)
        self.assertEqual(cache.get(card_a, "c"), 3)
        self.assertEqual(cache.get(card_b, "z"), 99)
        self.assertEqual(cache.get(card_b, "new"), "n")

        cache.rewind()

        self.assertEqual(cache.get(card_a, "a"), 1)
        self.assertEqual(cache.get(card_a, "b"), 2)
        self.assertEqual(cache.get(card_a, "c", None), None)
        self.assertEqual(cache.get(card_b, "z"), 9)
        self.assertEqual(cache.get(card_b, "new", None), None)

    def test_one_look_get_deletes_immediately_without_capture(self):
        card_a, _, cache = self._make_cards_and_cache()

        cache.set(card_a, "token", "abc")
        first_read = cache.get(card_a, "token", one_look=True)
        second_read = cache.get(card_a, "token", None)

        self.assertEqual(first_read, "abc")
        self.assertEqual(second_read, None)

    def test_one_look_get_under_capture_is_rollback_safe(self):
        card_a, _, cache = self._make_cards_and_cache()

        cache.set(card_a, "token", "abc")
        cache.capture()
        first_read = cache.get(card_a, "token", one_look=True)
        self.assertEqual(first_read, "abc")
        self.assertEqual(cache.get(card_a, "token", None), None)

        cache.rewind()
        self.assertEqual(cache.get(card_a, "token", None), "abc")

    def test_release_commits_capture_changes_and_clears_changelog(self):
        card_a, _, cache = self._make_cards_and_cache()

        cache.capture()
        cache.set(card_a, "score", 55)
        cache.release()

        self.assertEqual(cache.get(card_a, "score"), 55)

        cache.rewind()
        self.assertEqual(cache.get(card_a, "score"), 55)

    def test_wipe_under_capture_is_realtime_and_rollback_safe(self):
        card_a, _, cache = self._make_cards_and_cache()

        cache.set(card_a, "k1", 1)
        cache.set(card_a, "k2", 2)
        cache.set(card_a, "k3", 3)

        cache.capture()
        cache.wipe(card_a)

        self.assertEqual(cache.get(card_a, "k1", None), None)
        self.assertEqual(cache.get(card_a, "k2", None), None)
        self.assertEqual(cache.get(card_a, "k3", None), None)

        cache.rewind()

        self.assertEqual(cache.get(card_a, "k1"), 1)
        self.assertEqual(cache.get(card_a, "k2"), 2)
        self.assertEqual(cache.get(card_a, "k3"), 3)

    def test_multiple_capture_sessions_are_isolated(self):
        card_a, _, cache = self._make_cards_and_cache()

        cache.capture()
        cache.set(card_a, "x", 10)
        cache.release()

        cache.capture()
        cache.set(card_a, "x", 20)
        cache.delete(card_a, "x")
        self.assertEqual(cache.get(card_a, "x", None), None)
        cache.rewind()

        self.assertEqual(cache.get(card_a, "x"), 10)

    def test_insert_alter_delete_sequence_rewinds_to_absent_key(self):
        card_a, _, cache = self._make_cards_and_cache()

        cache.capture()
        cache.set(card_a, "seq", 1)
        cache.set(card_a, "seq", 2)
        cache.delete(card_a, "seq")

        self.assertEqual(cache.get(card_a, "seq", None), None)

        cache.rewind()
        self.assertEqual(cache.get(card_a, "seq", None), None)


if __name__ == "__main__":
    unittest.main()
