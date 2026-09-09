"""Unit tests for data ingestion, cleaning, validation, and hierarchy parsing."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from config import DEFAULT_DATA_PATH
from src.database import get_children, get_db_connection, get_series_by_id, init_db
from src.ingestion import IngestionValidationError, ingest_catalogue, validate_csv
from src.normalization import clean_text, extract_record_entities


class TestIngestion(unittest.TestCase):
    """Test suite for ingestion and schema integrity."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_db = Path(self.temp_dir.name) / "test_catalogue.db"
        self.vectors_path = Path(self.temp_dir.name) / "test_vectors.npy"
        self.vector_ids_path = Path(self.temp_dir.name) / "test_vector_ids.json"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_clean_text_removes_newlines_and_extra_spaces(self) -> None:
        dirty = "Cotton Yarn/Fabs./made-ups,\nHandloom   Products  etc."
        cleaned = clean_text(dirty)
        self.assertNotIn("\n", cleaned)
        self.assertNotIn("\r", cleaned)
        self.assertNotIn("  ", cleaned)
        self.assertEqual(cleaned, "Cotton Yarn/Fabs./made-ups, Handloom Products etc.")

    def test_extract_entities_aviation(self) -> None:
        rec = {
            "Title": "Monthly on time performance of Indigo at Delhi airport",
            "Category": "Civil Aviation",
            "SubCategory": "Airline Data",
        }
        entities = extract_record_entities(rec)
        self.assertEqual(entities["airline"], "Indigo")
        self.assertEqual(entities["airport"], "Delhi")

    def test_extract_entities_bangalore_spelling(self) -> None:
        rec = {
            "Title": "Monthly on time performance of Go Air at Banglore airport",
            "Category": "Civil Aviation",
            "SubCategory": "Airline Data",
        }
        entities = extract_record_entities(rec)
        self.assertEqual(entities["airline"], "Go Air")
        self.assertEqual(entities["airport"], "Banglore")

    def test_extract_entities_cashew(self) -> None:
        rec = {
            "Title": "Merchandise Exports - Cashew (Quick Estimate, Monthly, US Dollar)",
            "Category": "Foreign Trade",
            "SubCategory": "Merchandise Trade",
        }
        entities = extract_record_entities(rec)
        self.assertEqual(entities["commodity"], "Cashew")
        self.assertEqual(entities["flow"], "Exports")
        self.assertEqual(entities["calc_type"], "Monthly")

    def test_validation_nonexistent_file(self) -> None:
        with self.assertRaises(IngestionValidationError):
            validate_csv("non_existent_file_xyz.csv")

    def test_full_ingestion_and_counts(self) -> None:
        result = ingest_catalogue(
            csv_path=DEFAULT_DATA_PATH,
            db_path=self.test_db,
            build_vectors=False,
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["total_records"], 369)
        self.assertEqual(result["total_hierarchy_edges"], 340)

        # Verify SQLite tables
        conn = get_db_connection(self.test_db)
        cur = conn.execute("SELECT COUNT(*) FROM series;")
        self.assertEqual(cur.fetchone()[0], 369)

        cur = conn.execute("SELECT COUNT(*) FROM series_hierarchy;")
        self.assertEqual(cur.fetchone()[0], 340)

        cur = conn.execute("SELECT COUNT(*) FROM series WHERE discontinued = 'Y';")
        self.assertEqual(cur.fetchone()[0], 22)
        conn.close()

    def test_hierarchy_relationships(self) -> None:
        ingest_catalogue(
            csv_path=DEFAULT_DATA_PATH,
            db_path=self.test_db,
            build_vectors=False,
        )
        # Parent Metro Airports - Indigo
        children = get_children("IFCAOTPINA11M", db_path=self.test_db)
        self.assertEqual(len(children), 10)
        child_ids = [c["identifier"] for c in children]
        self.assertIn("IFCAOTPIND11M", child_ids)  # Delhi
        self.assertIn("IFCAOTPINM11M", child_ids)  # Mumbai
        self.assertIn("IFCAOTPINB11M", child_ids)  # Bangalore


if __name__ == "__main__":
    unittest.main()
