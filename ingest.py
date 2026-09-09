"""CLI Entrypoint for Ingestion: python ingest.py --input series_catalogue_raw.csv [--db catalogue.db]"""

import argparse
import logging
import sys
from pathlib import Path

from config import DEFAULT_DATA_PATH, DEFAULT_DB_PATH
from src.ingestion import IngestionValidationError, ingest_catalogue

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ingest")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest series catalogue CSV into SQLite database and build search indexes."
    )
    parser.add_argument(
        "--input",
        "-i",
        dest="input_file",
        required=True,
        type=str,
        help="Path to input CSV file (e.g. series_catalogue_raw.csv)",
    )
    parser.add_argument(
        "--db",
        dest="db_path",
        default=str(DEFAULT_DB_PATH),
        type=str,
        help=f"Target SQLite database path (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--no-vectors",
        action="store_true",
        help="Skip dense vector embedding generation (lexical index only).",
    )

    args = parser.parse_args()

    input_path = Path(args.input_file)
    db_path = Path(args.db_path)

    try:
        result = ingest_catalogue(
            csv_path=input_path,
            db_path=db_path,
            build_vectors=not args.no_vectors,
        )
        print(f"\n[SUCCESS] Ingestion completed successfully!")
        print(f"  - Database: {result['db_path']}")
        print(f"  - Total Series Loaded: {result['total_records']}")
        print(f"  - Total Hierarchy Edges: {result['total_hierarchy_edges']}")
    except IngestionValidationError as e:
        logger.error(f"Input validation error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected ingestion failure: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
