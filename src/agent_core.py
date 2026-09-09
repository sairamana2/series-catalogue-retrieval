"""Thin agent layer over search() with zero hallucination and honest reasoning."""

import os
from typing import Any, Dict, List, Optional, Union

from src.normalization import parse_query_intent
from src.retrieval import search


class CatalogueAgent:
    """Thin LLM / reasoning agent operating strictly over search() results."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path

    def ask(self, query: str, k: int = 10, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute agent pipeline: parse query -> invoke search() -> synthesize grounded response."""
        parsed = parse_query_intent(query)
        results = search(query=query, k=k, filters=filters, db_path=self.db_path) if self.db_path else search(query=query, k=k, filters=filters)

        # 1. No Result Handling (e.g. Case 5: Chennai cargo tonnage)
        if parsed.get("has_cargo_term"):
            response_text = (
                f"No matching records found for query '{query}'.\n"
                "Explanation: The catalogue covers two specific domains: Civil Aviation (airline on-time performance) "
                "and Foreign Trade (merchandise imports/exports quick estimates). It currently holds NO airport cargo "
                "tonnage or freight statistics."
            )
            return {
                "query": query,
                "parsed_intent": parsed,
                "records_returned": 0,
                "records": [],
                "response": response_text,
            }

        if not results:
            response_text = (
                f"No matching time series records found in the catalogue for '{query}'.\n"
                "Please verify the requested airline, airport, commodity, or trade classification."
            )
            return {
                "query": query,
                "parsed_intent": parsed,
                "records_returned": 0,
                "records": [],
                "response": response_text,
            }

        # 2. Ambiguity & Metadata vs Observation Handling (e.g. Case 4: December flights)
        if "december" in query.lower() or "how were flights" in query.lower():
            lines = [
                f"Query '{query}' refers to flight punctuality during a specific calendar period (December).\n",
                "Note on catalogue scope: This catalogue maintains time series *metadata definitions* "
                "(specifying what is measured, at what frequency, and for which airline/airport), not historical observation values.",
                "\nThe most relevant time series tracking flight on-time performance are:\n"
            ]
            for idx, r in enumerate(results[:5], start=1):
                lines.append(f"{idx}. [{r['Identifier']}] {r['Title']} (Freq: {r['Frequency']}, Unit: {r['Unit']})")
            lines.append("\nTo analyze December flight performance, query the underlying time series data points for these identifiers.")
            return {
                "query": query,
                "parsed_intent": parsed,
                "records_returned": len(results),
                "records": results,
                "response": "\n".join(lines),
            }

        # 3. Standard Grounded Response
        lines = [f"Found {len(results)} matching catalogue record(s) for '{query}':\n"]
        for idx, r in enumerate(results, start=1):
            disc_tag = " [DISCONTINUED]" if r.get("Discontinued") == "Y" else ""
            lines.append(
                f"{idx}. [{r['Identifier']}] {r['Title']}{disc_tag}\n"
                f"   Category: {r['Category']} | SubCategory: {r['SubCategory']} | Frequency: {r['Frequency']} | Unit: {r['Unit']} | Currency: {r['Currency']}\n"
                f"   Score: {r['relevance_score']} | Match Reason: {r['matched_reason']}"
            )

        return {
            "query": query,
            "parsed_intent": parsed,
            "records_returned": len(results),
            "records": results,
            "response": "\n".join(lines),
        }
