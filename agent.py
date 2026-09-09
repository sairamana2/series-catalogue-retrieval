"""CLI and Python API Entrypoint for Catalogue Agent.

Usage:
    python agent.py "IndiGo on-time performance at Delhi"
    python agent.py "Chennai cargo tonnage"
    python agent.py "how were flights in December?"
"""

import argparse
import sys
from typing import Any, Dict, Optional

from src.agent_core import CatalogueAgent


def ask(query: str, k: int = 10, filters: Optional[Dict[str, Any]] = None, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Ask the thin catalogue agent a natural language question."""
    agent = CatalogueAgent(db_path=db_path)
    return agent.ask(query=query, k=k, filters=filters)


def main() -> None:
    parser = argparse.ArgumentParser(description="Thin agent layer over catalogue search.")
    parser.add_argument("query", type=str, help="Question to ask the agent")
    parser.add_argument("--k", type=int, default=10, help="Number of records to retrieve (default: 10)")
    parser.add_argument("--db", type=str, default=None, help="Optional SQLite database path")

    args = parser.parse_args()

    agent = CatalogueAgent(db_path=args.db)
    response = agent.ask(query=args.query, k=args.k)

    print(f"\n=======================================================")
    print(f"USER QUERY: {args.query}")
    print(f"=======================================================\n")
    print(response["response"])
    print(f"\n(Total records retrieved from store: {response['records_returned']})\n")


if __name__ == "__main__":
    main()
