import unittest

from ...testing.helpers import core_listeners
from ..listeners import default_core_listeners


class DefaultCoreListenersTests(unittest.TestCase):
    def test_matches_testing_helpers_core_listeners_exactly(self):
        '''These two lists are intentionally, independently maintained (see listeners.py's
        docstring) - this test is the tripwire that catches them drifting apart.'''
        self.assertEqual(set(default_core_listeners()), set(core_listeners()))
        self.assertEqual(len(default_core_listeners()), len(core_listeners()))


if __name__ == "__main__":
    unittest.main()
