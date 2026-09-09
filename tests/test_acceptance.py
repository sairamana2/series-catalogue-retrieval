"""Direct unit tests verifying all five mandatory acceptance cases."""

import unittest
from pathlib import Path

from config import DEFAULT_DATA_PATH
from src.ingestion import ingest_catalogue
from src.retrieval import search


class TestAcceptanceCases(unittest.TestCase):
    """Test suite for the 5 mandatory acceptance cases."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.db_path = Path("catalogue.db")
        if not cls.db_path.exists():
            ingest_catalogue(
                csv_path=DEFAULT_DATA_PATH,
                db_path=cls.db_path,
                build_vectors=True,
            )

    @classmethod
    def tearDownClass(cls) -> None:
        pass

    def test_case_1_delhi_indigo_exact_one(self) -> None:
        """Case 1: 'IndiGo on-time performance at Delhi' -> Exactly one record: IFCAOTPIND11M."""
        res = search("IndiGo on-time performance at Delhi", k=10, db_path=self.db_path)
        self.assertEqual(len(res), 1, f"Expected exactly 1 record, got {len(res)}: {[r['Identifier'] for r in res]}")
        self.assertEqual(res[0]["Identifier"], "IFCAOTPIND11M")

    def test_case_2_cashew_dollar_ranked_first(self) -> None:
        """Case 2: 'monthly cashew exports in dollars' -> EXMTXDCHWQ11M ranked first."""
        res = search("monthly cashew exports in dollars", k=10, db_path=self.db_path)
        self.assertTrue(len(res) > 0)
        self.assertEqual(res[0]["Identifier"], "EXMTXDCHWQ11M")
        # Check that it beats rupee and cumulative records
        top_ids = [r["Identifier"] for r in res[:4]]
        self.assertIn("EXMTXDCHCQ11M", top_ids)
        self.assertIn("EXMTXRCHWQ11M", top_ids)

    def test_case_3_indigo_all_12_records(self) -> None:
        """Case 3: 'IndiGo punctuality' -> All 12 IndiGo on-time records."""
        res = search("IndiGo punctuality", k=15, db_path=self.db_path)
        known_12 = {
            "IFCAOTPINA11M", "IFCAOTPINM11M", "IFCAOTPIND11M", "IFCAOTPINB11M",
            "IFCAOTPINH11M", "IFCAOTPINC11M", "IFCAOTPINK11M", "IFCAOTPINE11M",
            "IFCAOTPING11M", "IFCAOTPINI11M", "IFCAOTPINL11M", "IFCAOTPIDG11D"
        }
        retrieved_ids = [r["Identifier"] for r in res]
        self.assertEqual(len(retrieved_ids), 12)
        self.assertEqual(set(retrieved_ids), known_12)
        # Parent aggregate should rank first
        self.assertEqual(retrieved_ids[0], "IFCAOTPINA11M")

    def test_case_4_december_flights(self) -> None:
        """Case 4: 'how were flights in December?' -> Returns flight performance series."""
        res = search("how were flights in December?", k=10, db_path=self.db_path)
        self.assertTrue(len(res) > 0)
        self.assertTrue(all(r["Category"] == "Civil Aviation" for r in res))

    def test_case_5_chennai_cargo_zero_hallucination(self) -> None:
        """Case 5: 'Chennai cargo tonnage' -> No cargo records exist; returns 0 records."""
        res = search("Chennai cargo tonnage", k=10, db_path=self.db_path)
        self.assertEqual(len(res), 0, f"Expected 0 records, got: {[r['Identifier'] for r in res]}")


if __name__ == "__main__":
    unittest.main()
