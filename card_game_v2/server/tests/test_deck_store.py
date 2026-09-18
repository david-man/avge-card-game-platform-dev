import asyncio
import tempfile
import unittest
from pathlib import Path

from ...constants import CARDS_PER_DECK
from .. import deck_rules
from ..deck_store import DeckStore


def _legal_deck(character: str = "AshleyToby") -> list[str]:
    items = [
        "AVGEBirb", "AnnotatedScore", "BAIEmail", "BUOStand", "Camera", "CastReserve",
        "ConcertProgram", "ConcertRoster", "ConcertTicket", "CorruptedMusescoreFile",
        "DressRehearsalRoster", "FoldingStand", "IceSkates", "MatchaLatte", "MikuOtamatone",
        "Otamatone", "PrintedScore", "RaffleTicket", "StandardMusescoreFile",
    ]
    deck = [character] + items
    assert len(deck) == CARDS_PER_DECK
    return deck


class DeckStoreTestBase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.path = Path(self._tmpdir.name) / "decks.sqlite3"
        self.store = DeckStore(self.path)


class CreateAndListTests(DeckStoreTestBase):
    async def test_create_then_list_round_trips_exactly(self):
        deck = _legal_deck()
        created = await self.store.create_deck("acct-1", "My Deck", deck)
        self.assertEqual(created.name, "My Deck")
        self.assertEqual(created.cards, deck)

        listed = await self.store.list_decks("acct-1")
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0].deck_id, created.deck_id)
        self.assertEqual(listed[0].cards, deck)

    async def test_get_deck_returns_none_for_a_missing_id(self):
        self.assertIsNone(await self.store.get_deck("acct-1", "no-such-id"))

    async def test_create_validates_the_deck(self):
        with self.assertRaises(deck_rules.DeckValidationError):
            await self.store.create_deck("acct-1", "Bad Deck", ["AshleyToby"])

    async def test_create_validates_the_name(self):
        with self.assertRaises(deck_rules.DeckValidationError):
            await self.store.create_deck("acct-1", "   ", _legal_deck())


class DeckLimitTests(DeckStoreTestBase):
    async def test_the_eleventh_deck_is_rejected(self):
        for i in range(deck_rules.MAX_DECKS_PER_ACCOUNT):
            await self.store.create_deck("acct-1", f"Deck {i}", _legal_deck())
        with self.assertRaises(deck_rules.DeckLimitError):
            await self.store.create_deck("acct-1", "One Too Many", _legal_deck())

    async def test_deleting_one_frees_up_a_slot(self):
        created = []
        for i in range(deck_rules.MAX_DECKS_PER_ACCOUNT):
            created.append(await self.store.create_deck("acct-1", f"Deck {i}", _legal_deck()))
        await self.store.delete_deck("acct-1", created[0].deck_id)
        # Should no longer raise.
        await self.store.create_deck("acct-1", "Replacement", _legal_deck())

    async def test_concurrent_creates_never_exceed_the_cap(self):
        # The single most important test in this module: proves the 10-deck cap is enforced by a
        # real atomic transaction (BEGIN IMMEDIATE in deck_store.py), not a check-then-insert race
        # - asyncio.to_thread calls genuinely run on separate worker threads and can interleave,
        # unlike AccountStore's single-event-loop check-then-insert trick.
        results = await asyncio.gather(
            *(
                self.store.create_deck("acct-1", f"Deck {i}", _legal_deck())
                for i in range(deck_rules.MAX_DECKS_PER_ACCOUNT + 2)
            ),
            return_exceptions=True,
        )
        successes = [r for r in results if not isinstance(r, BaseException)]
        failures = [r for r in results if isinstance(r, BaseException)]
        self.assertEqual(len(successes), deck_rules.MAX_DECKS_PER_ACCOUNT)
        self.assertEqual(len(failures), 2)
        for failure in failures:
            self.assertIsInstance(failure, deck_rules.DeckLimitError)
        listed = await self.store.list_decks("acct-1")
        self.assertEqual(len(listed), deck_rules.MAX_DECKS_PER_ACCOUNT)

    async def test_the_cap_is_per_account(self):
        for i in range(deck_rules.MAX_DECKS_PER_ACCOUNT):
            await self.store.create_deck("acct-1", f"Deck {i}", _legal_deck())
        # A different account isn't affected by acct-1 already being at the cap.
        created = await self.store.create_deck("acct-2", "Deck", _legal_deck())
        self.assertIsNotNone(created)


class UpdateDeleteOwnershipTests(DeckStoreTestBase):
    async def test_update_against_another_accounts_deck_returns_none(self):
        deck = await self.store.create_deck("acct-1", "Mine", _legal_deck())
        result = await self.store.update_deck("acct-2", deck.deck_id, "Stolen", _legal_deck())
        self.assertIsNone(result)
        # And the original is untouched.
        still_mine = await self.store.get_deck("acct-1", deck.deck_id)
        assert still_mine is not None
        self.assertEqual(still_mine.name, "Mine")

    async def test_update_own_deck_changes_name_and_cards(self):
        deck = await self.store.create_deck("acct-1", "Original", _legal_deck())
        new_cards = _legal_deck("EmilyWang")
        updated = await self.store.update_deck("acct-1", deck.deck_id, "Renamed", new_cards)
        assert updated is not None
        self.assertEqual(updated.name, "Renamed")
        self.assertEqual(updated.cards, new_cards)

    async def test_delete_against_another_accounts_deck_returns_false(self):
        deck = await self.store.create_deck("acct-1", "Mine", _legal_deck())
        self.assertFalse(await self.store.delete_deck("acct-2", deck.deck_id))
        self.assertIsNotNone(await self.store.get_deck("acct-1", deck.deck_id))

    async def test_delete_own_deck_removes_it(self):
        deck = await self.store.create_deck("acct-1", "Mine", _legal_deck())
        self.assertTrue(await self.store.delete_deck("acct-1", deck.deck_id))
        self.assertIsNone(await self.store.get_deck("acct-1", deck.deck_id))


class SelectedDeckTests(DeckStoreTestBase):
    async def test_selecting_another_accounts_deck_fails_and_leaves_selection_untouched(self):
        mine = await self.store.create_deck("acct-1", "Mine", _legal_deck())
        theirs = await self.store.create_deck("acct-2", "Theirs", _legal_deck())
        await self.store.set_selected_deck("acct-1", mine.deck_id)

        ok = await self.store.set_selected_deck("acct-1", theirs.deck_id)
        self.assertFalse(ok)
        self.assertEqual(await self.store.get_selected_deck_id("acct-1"), mine.deck_id)

    async def test_selecting_own_deck_and_reading_it_back(self):
        deck = await self.store.create_deck("acct-1", "Mine", _legal_deck())
        self.assertTrue(await self.store.set_selected_deck("acct-1", deck.deck_id))
        self.assertEqual(await self.store.get_selected_deck_id("acct-1"), deck.deck_id)
        selected = await self.store.get_selected_deck("acct-1")
        assert selected is not None
        self.assertEqual(selected.deck_id, deck.deck_id)

    async def test_no_selection_by_default(self):
        await self.store.create_deck("acct-1", "Mine", _legal_deck())
        self.assertIsNone(await self.store.get_selected_deck_id("acct-1"))
        self.assertIsNone(await self.store.get_selected_deck("acct-1"))

    async def test_deleting_the_selected_deck_clears_the_selection(self):
        deck = await self.store.create_deck("acct-1", "Mine", _legal_deck())
        await self.store.set_selected_deck("acct-1", deck.deck_id)
        await self.store.delete_deck("acct-1", deck.deck_id)
        self.assertIsNone(await self.store.get_selected_deck_id("acct-1"))

    async def test_selecting_none_clears_the_selection(self):
        deck = await self.store.create_deck("acct-1", "Mine", _legal_deck())
        await self.store.set_selected_deck("acct-1", deck.deck_id)
        await self.store.set_selected_deck("acct-1", None)
        self.assertIsNone(await self.store.get_selected_deck_id("acct-1"))


class PersistenceTests(DeckStoreTestBase):
    async def test_a_second_store_on_the_same_path_sees_the_same_rows(self):
        deck = await self.store.create_deck("acct-1", "Mine", _legal_deck())
        second_store = DeckStore(self.path)
        reread = await second_store.get_deck("acct-1", deck.deck_id)
        assert reread is not None
        self.assertEqual(reread.cards, deck.cards)


if __name__ == "__main__":
    unittest.main()
