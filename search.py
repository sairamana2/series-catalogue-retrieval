"""CLI and Python API Entrypoint for Catalogue Search.

Usage:
    python search.py "monthly cashew exports in dollars" --k 10
    python search.py "IndiGo on-time performance at Delhi" --mode hybrid
    python search.py "IndiGo punctuality" --frequency Monthly
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from tabulate import tabulate

from config import DEFAULT_DB_PATH
from src.retrieval import search as core_search


def search(
    query: str,
    k: int = 10,
    filters: Optional[Dict[str, Any]] = None,
    mode: str = "hybrid",
    db_path: Union[str, Path] = DEFAULT_DB_PATH,
) -> List[Dict[str, Any]]:
    """Public Search API returning ranked catalogue records.

    Each result dictionary contains at minimum:
        Identifier, Title, Category, SubCategory, Frequency, Unit
    and also carries:
        Currency, Discontinued, relevance_score, matched_reason, ranking_method.
    """
    return core_search(query=query, k=k, filters=filters, mode=mode, db_path=db_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Search time series catalogue by natural language query.")
    parser.add_argument("query", type=str, help="Search query string")
    parser.add_argument("--k", type=int, default=10, help="Number of results to return (default: 10)")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["hybrid", "lexical", "vector"],
        default="hybrid",
        help="Retrieval strategy (default: hybrid)",
    )
    parser.add_argument("--frequency", type=str, help="Filter by Frequency (e.g. Monthly, Daily)")
    parser.add_argument("--category", type=str, help="Filter by Category (e.g. 'Civil Aviation', 'Foreign Trade')")
    parser.add_argument("--db", type=str, default=str(DEFAULT_DB_PATH), help="Path to database")

    args = parser.parse_args()

    filters: Dict[str, Any] = {}
    if args.frequency:
        filters["Frequency"] = args.frequency
    if args.category:
        filters["Category"] = args.category

    results = search(query=args.query, k=args.k, filters=filters or None, mode=args.mode, db_path=args.db)

    print(f"\nSearch Query: '{args.query}' | Mode: {args.mode} | Returned: {len(results)} records\n")

    if not results:
        print("No matching records found in catalogue.")
        return

    table_data = []
    for idx, r in enumerate(results, start=1):
        table_data.append([
            idx,
            r["Identifier"],
            r["Title"][:55] + "..." if len(r["Title"]) > 55 else r["Title"],
            r["Category"],
            r["Frequency"],
            r["Unit"],
            r["Currency"],
            r["Discontinued"],
            f"{r['relevance_score']:.3f}",
            r["matched_reason"][:30],
        ])

    headers = ["#", "Identifier", "Title", "Category", "Frequency", "Unit", "Currency", "Disc", "Score", "Reason"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))


if __name__ == "__main__":
    main()
