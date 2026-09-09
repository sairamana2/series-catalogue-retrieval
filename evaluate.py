"""Comprehensive Acceptance and Regression Evaluation Suite.

Runs all 5 mandatory acceptance cases and additional edge-case queries,
evaluating Lexical vs Vector vs Hybrid retrieval modes.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from tabulate import tabulate

from config import DEFAULT_DB_PATH
from search import search


def run_acceptance_cases(db_path: Path = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """Execute and evaluate all five mandatory acceptance cases."""
    print("\n" + "=" * 75)
    print("MANDATORY ACCEPTANCE CASES EVALUATION")
    print("=" * 75)

    report: Dict[str, Any] = {}

    # -------------------------------------------------------------
    # Case 1: IndiGo on-time performance at Delhi
    # Expected: Exactly one record: IFCAOTPIND11M
    # -------------------------------------------------------------
    q1 = "IndiGo on-time performance at Delhi"
    res1 = search(q1, k=10, db_path=db_path)
    ids1 = [r["Identifier"] for r in res1]
    pass1 = (len(ids1) == 1 and ids1[0] == "IFCAOTPIND11M")
    report["case_1"] = {
        "query": q1,
        "expected": "Exactly one record: IFCAOTPIND11M",
        "actual": ids1,
        "passed": pass1,
        "details": res1[0] if res1 else None,
    }
    print(f"\n[CASE 1] Query: '{q1}'")
    print(f"  Expected: Exactly one record: IFCAOTPIND11M")
    print(f"  Actual:   {ids1} (Count: {len(ids1)})")
    print(f"  Status:   {'PASSED' if pass1 else 'FAILED'}")
    if res1:
        print(f"  Top Match: [{res1[0]['Identifier']}] {res1[0]['Title']} (Score: {res1[0]['relevance_score']})")

    # -------------------------------------------------------------
    # Case 2: monthly cashew exports in dollars
    # Expected: EXMTXDCHWQ11M ranked first. Four cashew records exist.
    # -------------------------------------------------------------
    q2 = "monthly cashew exports in dollars"
    res2 = search(q2, k=10, db_path=db_path)
    ids2 = [r["Identifier"] for r in res2]
    pass2 = (len(ids2) > 0 and ids2[0] == "EXMTXDCHWQ11M")
    report["case_2"] = {
        "query": q2,
        "expected": "EXMTXDCHWQ11M ranked first among cashew records",
        "actual_top": ids2[0] if ids2 else None,
        "actual_ids": ids2[:4],
        "passed": pass2,
        "cashew_ranking": [
            {"id": r["Identifier"], "score": r["relevance_score"], "title": r["Title"]}
            for r in res2 if "cashew" in r["Title"].lower()
        ],
    }
    print(f"\n[CASE 2] Query: '{q2}'")
    print(f"  Expected: EXMTXDCHWQ11M ranked first")
    print(f"  Actual:   Rank 1 is {ids2[0] if ids2 else 'None'}")
    print(f"  Status:   {'PASSED' if pass2 else 'FAILED'}")
    print("  Cashew Records Breakdown:")
    for idx, r in enumerate(res2[:4], start=1):
        print(f"    {idx}. [{r['Identifier']}] {r['Title']} | Freq={r['Frequency']} | Unit={r['Unit']} | Curr={r['Currency']} | Score={r['relevance_score']}")

    # -------------------------------------------------------------
    # Case 3: IndiGo punctuality
    # Expected: All 12 IndiGo on-time records in defendable order
    # -------------------------------------------------------------
    q3 = "IndiGo punctuality"
    res3 = search(q3, k=15, db_path=db_path)
    ids3 = [r["Identifier"] for r in res3]
    known_indigo_12 = {
        "IFCAOTPINA11M", "IFCAOTPINM11M", "IFCAOTPIND11M", "IFCAOTPINB11M",
        "IFCAOTPINH11M", "IFCAOTPINC11M", "IFCAOTPINK11M", "IFCAOTPINE11M",
        "IFCAOTPING11M", "IFCAOTPINI11M", "IFCAOTPINL11M", "IFCAOTPIDG11D"
    }
    retrieved_indigo = [i for i in ids3 if i in known_indigo_12]
    pass3 = (len(retrieved_indigo) == 12 and len(ids3) == 12)
    report["case_3"] = {
        "query": q3,
        "expected": "All 12 IndiGo on-time records in deterministic, defendable order",
        "actual_count": len(retrieved_indigo),
        "actual_order": ids3,
        "passed": pass3,
        "order_details": [
            {"rank": idx, "id": r["Identifier"], "title": r["Title"], "score": r["relevance_score"]}
            for idx, r in enumerate(res3, start=1)
        ],
    }
    print(f"\n[CASE 3] Query: '{q3}'")
    print(f"  Expected: All 12 IndiGo on-time records")
    print(f"  Actual:   Retrieved {len(retrieved_indigo)}/12 IndiGo records (Total returned: {len(ids3)})")
    print(f"  Status:   {'PASSED' if pass3 else 'FAILED'}")
    print("  Deterministic Returned Order:")
    for idx, r in enumerate(res3, start=1):
        print(f"    {idx:>2}. [{r['Identifier']}] {r['Title']} (Score: {r['relevance_score']})")

    # -------------------------------------------------------------
    # Case 4: how were flights in December?
    # Expected: Civil Aviation series returned; metadata vs observation clarification
    # -------------------------------------------------------------
    q4 = "how were flights in December?"
    res4 = search(q4, k=10, db_path=db_path)
    pass4 = (len(res4) > 0 and all(r["Category"] == "Civil Aviation" for r in res4))
    report["case_4"] = {
        "query": q4,
        "expected": "Civil Aviation on-time performance series; metadata vs observation distinction",
        "actual_count": len(res4),
        "actual_top": [r["Identifier"] for r in res4[:3]],
        "passed": pass4,
        "top_records": [
            {"id": r["Identifier"], "title": r["Title"], "score": r["relevance_score"]}
            for r in res4[:5]
        ],
    }
    print(f"\n[CASE 4] Query: '{q4}'")
    print(f"  Expected: Returns relevant Civil Aviation flight performance series")
    print(f"  Actual:   Returned {len(res4)} flight performance series (All Category='Civil Aviation')")
    print(f"  Status:   {'PASSED' if pass4 else 'FAILED'}")
    for idx, r in enumerate(res4[:3], start=1):
        print(f"    {idx}. [{r['Identifier']}] {r['Title']}")

    # -------------------------------------------------------------
    # Case 5: Chennai cargo tonnage
    # Expected: Zero cargo records exist; honest 0-result / no hallucination
    # -------------------------------------------------------------
    q5 = "Chennai cargo tonnage"
    res5 = search(q5, k=10, db_path=db_path)
    pass5 = (len(res5) == 0)
    report["case_5"] = {
        "query": q5,
        "expected": "Zero records returned (no cargo tonnage exists in catalogue)",
        "actual_count": len(res5),
        "passed": pass5,
        "returned": res5,
    }
    print(f"\n[CASE 5] Query: '{q5}'")
    print(f"  Expected: Zero records (no cargo tonnage data exists)")
    print(f"  Actual:   {len(res5)} records returned")
    print(f"  Status:   {'PASSED' if pass5 else 'FAILED'}")
    if res5:
        print("  WARNING: Returned false positives:")
        for r in res5:
            print(f"    - [{r['Identifier']}] {r['Title']}")

    return report


def run_mode_comparison(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Compare Lexical, Vector, and Hybrid retrieval across test queries."""
    print("\n" + "=" * 75)
    print("RETRIEVAL MODE COMPARISON: LEXICAL vs VECTOR vs HYBRID")
    print("=" * 75)

    test_queries = [
        ("IndiGo on-time performance at Delhi", "IFCAOTPIND11M"),
        ("monthly cashew exports in dollars", "EXMTXDCHWQ11M"),
        ("IndiGo punctuality", "IFCAOTPINA11M"),
        ("IndiGo Bangalore punctuality", "IFCAOTPINB11M"),
        ("SpiceJet punctuality at Mumbai", "IFCAOTPSJM11M"),
        ("cumulative cashew exports in dollars", "EXMTXDCHCQ11M"),
        ("monthly cashew exports in rupees", "EXMTXRCHWQ11M"),
        ("Chennai cargo tonnage", "NONE"),
    ]

    table = []
    for query, expected_top in test_queries:
        lex = search(query, k=5, mode="lexical", db_path=db_path)
        vec = search(query, k=5, mode="vector", db_path=db_path)
        hyb = search(query, k=5, mode="hybrid", db_path=db_path)

        top_lex = lex[0]["Identifier"] if lex else "NONE"
        top_vec = vec[0]["Identifier"] if vec else "NONE"
        top_hyb = hyb[0]["Identifier"] if hyb else "NONE"

        table.append([
            query[:35],
            expected_top,
            top_lex,
            top_vec,
            top_hyb,
            "PASS" if top_hyb == expected_top else "FAIL",
        ])

    headers = ["Query", "Expected Rank 1", "Lexical Top", "Vector Top", "Hybrid Top", "Hybrid Status"]
    print(tabulate(table, headers=headers, tablefmt="grid"))


def main() -> None:
    report = run_acceptance_cases()
    run_mode_comparison()

    report_path = Path("evaluation_report.json")
    with open(report_path, mode="w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nSaved detailed evaluation report to {report_path.resolve()}\n")


if __name__ == "__main__":
    main()
