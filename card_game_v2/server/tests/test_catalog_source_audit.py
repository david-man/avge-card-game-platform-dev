import unittest

from ...catalog.audit_source_data import EXPECTED_HASHES, build_report


class CatalogSourceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = build_report()

    def test_source_hashes_are_exact(self):
        for filename, expected in EXPECTED_HASHES.items():
            self.assertEqual(self.report["source_hashes"][filename]["actual"], expected)

    def test_expected_counts(self):
        self.assertEqual(self.report["counts"]["source_characters"], 77)
        self.assertEqual(self.report["counts"]["source_noncharacters"], 46)
        self.assertEqual(self.report["counts"]["source_statuses"], 3)
        self.assertEqual(self.report["counts"]["registry_total"], 123)

    def test_all_deck_cards_are_accounted_for(self):
        for mismatches in self.report["identity_mismatches"].values():
            self.assertEqual(mismatches, [])
        self.assertEqual(self.report["stat_mismatches"], [])
        self.assertEqual(self.report["action_name_mismatches"], [])
        self.assertEqual(self.report["kind_mismatches"], [])

    def test_status_rows_are_audited_separately(self):
        self.assertEqual(self.report["status_rows"]["found"], ["Arranger", "Goon", "Maid"])
        self.assertEqual(self.report["status_rows"]["missing"], [])
        self.assertEqual(self.report["status_rows"]["unexpected"], [])


if __name__ == "__main__":
    unittest.main()
