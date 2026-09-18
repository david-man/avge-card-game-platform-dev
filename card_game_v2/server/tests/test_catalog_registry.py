import inspect
import unittest
from pathlib import Path

from ...avge_abstracts.AVGECard import AVGECard
from ...avge_abstracts.AVGEDeck import DeckType
from ...avge_abstracts.AVGEEnvironment import AVGEEnvironment
from ...catalog import registry
from ...constants import User
from ...testing.helpers import TestIO, core_listeners
from .. import serialization

_CATALOG_DIR = Path(registry.__file__).resolve().parent


def _file_count(subdir: str) -> int:
    # Every card lives one class per file, filename == class_name - counting .py files under each
    # category directory (excluding __init__.py) gives an independent, filesystem-derived
    # expectation the registry's own walk can be checked against, so the two can't silently drift
    # together if a file is added without updating a hand-maintained count somewhere.
    return sum(
        1 for p in (_CATALOG_DIR / subdir).glob("*.py")
        if p.name != "__init__.py"
    )


class AllEntriesTests(unittest.TestCase):
    def test_per_kind_counts_match_the_filesystem(self):
        entries = registry.all_entries()
        counts = {}
        for e in entries:
            counts[e.kind] = counts.get(e.kind, 0) + 1
        self.assertEqual(counts[registry.CardKind.ITEM], _file_count("items"))
        self.assertEqual(counts[registry.CardKind.SUPPORTER], _file_count("supporters"))
        self.assertEqual(counts[registry.CardKind.TOOL], _file_count("tools"))
        self.assertEqual(counts[registry.CardKind.STADIUM], _file_count("stadiums"))
        character_files = sum(
            _file_count(f"characters/{sub}")
            for sub in ("brass", "choir", "guitar", "percussion", "piano", "strings", "woodwinds")
        )
        self.assertEqual(counts[registry.CardKind.CHARACTER], character_files)

    def test_no_duplicate_class_names(self):
        names = [e.class_name for e in registry.all_entries()]
        self.assertEqual(len(names), len(set(names)))

    def test_class_name_matches_the_actual_class(self):
        for e in registry.all_entries():
            self.assertEqual(e.class_name, e.card_class.__name__)

    def test_no_abstract_base_classes_leak_in(self):
        for e in registry.all_entries():
            self.assertFalse(inspect.isabstract(e.card_class))
            self.assertTrue(issubclass(e.card_class, AVGECard))

    def test_no_status_effect_classes_are_included(self):
        # status_effects/ modules aren't AVGECard subclasses at all - not deck-buildable, and
        # should never appear here.
        for e in registry.all_entries():
            self.assertNotIn("status_effects", e.card_class.__module__)

    def test_characters_have_a_subtype_others_dont(self):
        for e in registry.all_entries():
            if e.kind is registry.CardKind.CHARACTER:
                self.assertIsNotNone(e.subtype)
                self.assertIn(
                    e.subtype,
                    {"brass", "choir", "guitar", "percussion", "piano", "strings", "woodwinds"},
                )
            else:
                self.assertIsNone(e.subtype)

    def test_all_entries_is_cached(self):
        self.assertIs(registry.all_entries(), registry.all_entries())

    def test_entry_lookup(self):
        self.assertIsNone(registry.entry("NotACard"))
        found = registry.entry("AshleyToby")
        self.assertIsNotNone(found)
        assert found is not None
        self.assertEqual(found.kind, registry.CardKind.CHARACTER)
        self.assertEqual(found.subtype, "strings")

    def test_card_class_lookup(self):
        self.assertIsNone(registry.card_class("NotACard"))
        self.assertIsNotNone(registry.card_class("AshleyToby"))


class FullCatalogSmokeTests(unittest.TestCase):
    '''The cheapest possible guard against a catalog card that can't be instantiated or
    serialized once mixed decks (server/deck_store.py onward) make every card in the catalog
    reachable in a real game, not just the 9 hand-picked character classes the old preset pool
    used.'''

    def test_every_catalog_card_constructs_and_serializes(self):
        classes = [e.card_class for e in registry.all_entries()]
        decks = {User.PLAYER_1: classes, User.PLAYER_2: list(classes)}
        env = AVGEEnvironment(TestIO(), decks, core_listeners())
        seen_names = set()
        for player in env.players.values():
            for card in player.card_piles[DeckType.DECK].cards_holding:
                wire = serialization.card_to_wire(card)
                seen_names.add(wire["class_name"])
        self.assertEqual(seen_names, {e.class_name for e in registry.all_entries()})


if __name__ == "__main__":
    unittest.main()
