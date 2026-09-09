"""Unit tests for search API, normalization, filtering, and edge cases."""

import unittest
from pathlib import Path

from config import DEFAULT_DATA_PATH
from src.ingestion import ingest_catalogue
from src.normalization import parse_query_intent
from src.retrieval import search


class TestSearch(unittest.TestCase):
    """Test suite for search, normalization, filters, and edge cases."""

    @classmethod
    def setUpClass(cls) -> None:
        # Ingest once for search tests
        cls.db_path = Path("test_search_catalogue.db")
        cls.vec_path = Path("test_search_vectors.npy")
        cls.vec_id_path = Path("test_search_vector_ids.json")
        ingest_catalogue(
            csv_path=DEFAULT_DATA_PATH,
            db_path=cls.db_path,
            build_vectors=False,  # Lexical tests work without vectors
        )

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.db_path.exists():
            cls.db_path.unlink()
        if cls.vec_path.exists():
            cls.vec_path.unlink()
        if cls.vec_id_path.exists():
            cls.vec_id_path.unlink()

    def test_parse_query_intent(self) -> None:
        intent = parse_query_intent("monthly cashew exports in dollars")
        self.assertEqual(intent["commodity"], "Cashew")
        self.assertEqual(intent["flow"], "Exports")
        self.assertEqual(intent["frequency"], "Monthly")
        self.assertEqual(intent["currency"], "USD")
        self.assertEqual(intent["unit"], "US Dollar")

    def test_parse_query_intent_airline_airport(self) -> None:
        intent = parse_query_intent("IndiGo on-time performance at Bangalore")
        self.assertEqual(intent["airline"], "Indigo")
        self.assertEqual(intent["airport"], "Banglore")
        self.assertTrue(intent["is_punctuality_query"])

    def test_empty_query_returns_empty(self) -> None:
        res = search("", k=10, mode="lexical", db_path=self.db_path)
        self.assertEqual(res, [])
        res2 = search("   ", k=10, mode="lexical", db_path=self.db_path)
        self.assertEqual(res2, [])

    def test_negative_or_zero_k(self) -> None:
        res = search("cashew", k=0, mode="lexical", db_path=self.db_path)
        self.assertEqual(res, [])
        res2 = search("cashew", k=-5, mode="lexical", db_path=self.db_path)
        self.assertEqual(res2, [])

    def test_filtered_search(self) -> None:
        res = search(
            "on time performance",
            k=10,
            filters={"Frequency": "Daily"},
            mode="lexical",
            db_path=self.db_path,
        )
        self.assertTrue(len(res) > 0)
        self.assertTrue(all(r["Frequency"] == "Daily" for r in res))

    def test_spelling_variation_bangalore(self) -> None:
        res_canon = search("Indigo Banglore", k=5, mode="lexical", db_path=self.db_path)
        res_alias = search("Indigo Bangalore", k=5, mode="lexical", db_path=self.db_path)
        self.assertTrue(len(res_canon) > 0)
        self.assertTrue(len(res_alias) > 0)
        self.assertEqual(res_canon[0]["Identifier"], "IFCAOTPINB11M")
        self.assertEqual(res_alias[0]["Identifier"], "IFCAOTPINB11M")

    def test_deterministic_tie_breaking(self) -> None:
        q = "IndiGo punctuality"
        res1 = search(q, k=12, mode="lexical", db_path=self.db_path)
        res2 = search(q, k=12, mode="lexical", db_path=self.db_path)
        ids1 = [r["Identifier"] for r in res1]
        ids2 = [r["Identifier"] for r in res2]
        self.assertEqual(ids1, ids2)


if __name__ == "__main__":
    unittest.main()
