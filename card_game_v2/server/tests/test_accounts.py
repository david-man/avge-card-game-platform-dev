import asyncio
import tempfile
import unittest
from pathlib import Path

from ..accounts import AccountStore


class AccountStoreTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.path = Path(self._tmpdir.name) / "accounts.json"

    async def test_login_by_username_creates_a_new_account(self):
        store = AccountStore(self.path)
        account = await store.login_by_username("alice")
        self.assertIsNotNone(account)
        assert account is not None
        self.assertEqual(account.username, "alice")
        self.assertTrue(account.account_id)
        self.assertTrue(account.auth_token)

    async def test_repeat_login_returns_the_same_account_and_token(self):
        store = AccountStore(self.path)
        first = await store.login_by_username("alice")
        second = await store.login_by_username("alice")
        self.assertEqual(first, second)

    async def test_username_uniqueness_is_case_insensitive(self):
        store = AccountStore(self.path)
        lower = await store.login_by_username("alice")
        upper = await store.login_by_username("Alice")
        self.assertEqual(lower, upper)
        # Original typed casing of the FIRST login is preserved for display.
        assert lower is not None
        self.assertEqual(lower.username, "alice")

    async def test_whitespace_is_stripped(self):
        store = AccountStore(self.path)
        a = await store.login_by_username("alice")
        b = await store.login_by_username("  alice  ")
        self.assertEqual(a, b)

    async def test_empty_username_returns_none(self):
        store = AccountStore(self.path)
        self.assertIsNone(await store.login_by_username(""))
        self.assertIsNone(await store.login_by_username("   "))

    async def test_login_by_token_resolves(self):
        store = AccountStore(self.path)
        account = await store.login_by_username("alice")
        assert account is not None
        resolved = store.login_by_token(account.auth_token)
        self.assertEqual(resolved, account)

    def test_login_by_unknown_token_returns_none(self):
        store = AccountStore(self.path)
        self.assertIsNone(store.login_by_token("not-a-real-token"))

    async def test_persists_across_instances(self):
        store1 = AccountStore(self.path)
        account = await store1.login_by_username("alice")
        assert account is not None

        store2 = AccountStore(self.path)
        self.assertEqual(await store2.login_by_username("alice"), account)
        self.assertEqual(store2.login_by_token(account.auth_token), account)

    async def test_different_usernames_get_different_accounts(self):
        store = AccountStore(self.path)
        alice = await store.login_by_username("alice")
        bob = await store.login_by_username("bob")
        assert alice is not None and bob is not None
        self.assertNotEqual(alice.account_id, bob.account_id)
        self.assertNotEqual(alice.auth_token, bob.auth_token)

    async def test_concurrent_registration_of_the_same_new_username_does_not_race(self):
        '''Regression test for the race a prior version of login_by_username had: offloading the
        whole check-then-insert to a worker thread via asyncio.to_thread let two concurrent
        registrations of the same brand-new username interleave across real OS threads, so one of
        the two tokens could end up orphaned from _by_key. login_by_username now only offloads the
        _persist() write, keeping the check-then-insert itself on the event loop.'''
        store = AccountStore(self.path)
        first, second = await asyncio.gather(
            store.login_by_username("carol"), store.login_by_username("carol"),
        )
        assert first is not None and second is not None
        self.assertEqual(first.account_id, second.account_id)
        self.assertEqual(first.auth_token, second.auth_token)

        reloaded = AccountStore(self.path)
        self.assertEqual(await reloaded.login_by_username("carol"), first)


if __name__ == "__main__":
    unittest.main()
