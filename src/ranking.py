"""Scoring function, constraint boosting, and deterministic tie-breaking logic."""

from typing import Any, Dict, List, Optional, Tuple

from config import (
    CONFLICT_PENALTY,
    CONSTRAINT_BOOST_MEDIUM,
    CONSTRAINT_BOOST_STRONG,
    DISCONTINUED_PENALTY,
    RELEVANCE_SCORE_THRESHOLD,
)


def score_and_rank_candidates(
    candidates: List[Dict[str, Any]],
    parsed_intent: Dict[str, Any],
    k: int = 10,
    filters: Optional[Dict[str, Any]] = None,
    threshold: float = RELEVANCE_SCORE_THRESHOLD,
) -> List[Dict[str, Any]]:
    """Score candidates using multi-field boosts, constraint alignment, and deterministic tie-breaking."""
    # If the user queried for cargo tonnage, the catalogue holds 0 cargo series.
    # Return empty to avoid false-positive hallucinations.
    if parsed_intent.get("has_cargo_term"):
        return []

    req_airline = parsed_intent.get("airline")
    req_airport = parsed_intent.get("airport")
    req_commodity = parsed_intent.get("commodity")
    req_flow = parsed_intent.get("flow")
    req_calc_type = parsed_intent.get("calc_type")
    req_frequency = parsed_intent.get("frequency")
    req_currency = parsed_intent.get("currency")
    is_punctuality = parsed_intent.get("is_punctuality_query", False)

    scored_records: List[Dict[str, Any]] = []

    for rec in candidates:
        # Check external filters if provided
        if filters:
            match_filters = True
            for f_key, f_val in filters.items():
                rec_val = rec.get(f_key.lower()) or rec.get(f_key)
                if rec_val is None or str(rec_val).lower() != str(f_val).lower():
                    match_filters = False
                    break
            if not match_filters:
                continue

        base_score = float(rec.get("raw_retrieval_score", 0.0))
        boost = 0.0
        match_reasons: List[str] = []

        # 1. Airline constraint: if user explicitly specified an airline, reject other airlines
        rec_airline = rec.get("airline")
        if req_airline:
            if not rec_airline or rec_airline.lower() != req_airline.lower():
                continue
            boost += CONSTRAINT_BOOST_STRONG
            match_reasons.append(f"airline:{req_airline}")

        # 2. Airport constraint: if user explicitly specified an airport, reject other airports/aggregates
        rec_airport = rec.get("airport")
        if req_airport:
            if not rec_airport or rec_airport.lower() != req_airport.lower():
                continue
            boost += CONSTRAINT_BOOST_STRONG + 1.0
            match_reasons.append(f"airport:{req_airport}")

        # 3. Commodity constraint: if user explicitly specified a commodity, reject other commodities
        rec_commodity = rec.get("commodity")
        if req_commodity:
            if not rec_commodity or rec_commodity.lower() != req_commodity.lower():
                continue
            boost += CONSTRAINT_BOOST_STRONG + 1.0
            match_reasons.append(f"commodity:{req_commodity}")

        # 4. Trade Flow constraint (Exports vs Imports vs Trade Balance)
        rec_flow = rec.get("flow")
        if req_flow:
            if rec_flow and rec_flow.lower() == req_flow.lower():
                boost += CONSTRAINT_BOOST_MEDIUM
                match_reasons.append(f"flow:{req_flow}")
            elif rec_flow and rec_flow.lower() != req_flow.lower():
                boost -= CONFLICT_PENALTY

        # 5. Calculation Type (Monthly vs Cumulative)
        rec_calc = rec.get("calc_type")
        if req_calc_type:
            if rec_calc and rec_calc.lower() == req_calc_type.lower():
                boost += CONSTRAINT_BOOST_MEDIUM
                match_reasons.append(f"calculation:{req_calc_type}")
            elif rec_calc and rec_calc.lower() != req_calc_type.lower():
                boost -= CONSTRAINT_BOOST_MEDIUM

        # 6. Currency / Unit constraint (USD vs INR)
        rec_curr = rec.get("currency")
        if req_currency:
            if rec_curr and rec_curr.upper() == req_currency.upper():
                boost += CONSTRAINT_BOOST_STRONG
                match_reasons.append(f"currency:{req_currency}")
            elif rec_curr and rec_curr.upper() != req_currency.upper() and rec_curr != "NA":
                boost -= CONFLICT_PENALTY

        # 7. Frequency constraint
        rec_freq = rec.get("frequency")
        if req_frequency:
            if rec_freq and rec_freq.lower() == req_frequency.lower():
                boost += CONSTRAINT_BOOST_MEDIUM
                match_reasons.append(f"frequency:{req_frequency}")
            elif rec_freq and rec_freq.lower() != req_frequency.lower():
                boost -= CONSTRAINT_BOOST_MEDIUM

        # 8. Punctuality / Aviation domain intent
        if is_punctuality and rec.get("category") == "Civil Aviation":
            boost += 1.0
            match_reasons.append("metric:punctuality")

        # 9. Aggregate overview priority when airport is NOT requested
        if is_punctuality and not req_airport and rec.get("category") == "Civil Aviation":
            if rec.get("airport") == "Metro Airports":
                boost += 0.5  # Rank parent aggregate overview higher than individual airports
                match_reasons.append("hierarchy:metro_aggregate")
            elif rec.get("frequency") == "Monthly" and rec.get("airport"):
                boost += 0.2  # Individual monthly airports

        # 10. Discontinued series handling
        is_discontinued = (rec.get("discontinued") == "Y")
        if is_discontinued:
            # Check if user specifically requested a discontinued airline
            if req_airline in ["Go Air", "Vistara", "Air Asia", "AIX Connect"]:
                match_reasons.append("status:discontinued_requested")
            else:
                boost -= DISCONTINUED_PENALTY
                match_reasons.append("status:discontinued_penalty")

        final_score = base_score + boost
        if final_score < threshold:
            continue

        scored_rec = dict(rec)
        scored_rec["relevance_score"] = round(final_score, 4)
        scored_rec["matched_reason"] = ", ".join(match_reasons) if match_reasons else "lexical_semantic_similarity"
        scored_records.append(scored_rec)

    # Deterministic Tie-Breaking Key
    # 1. Higher relevance_score (descending)
    # 2. Active over discontinued (active=1, discontinued=0)
    # 3. Hierarchy depth: Parent aggregate (parent is None) first
    # 4. Canonical child hierarchy order (if present)
    # 5. Identifier (alphabetical ascending for total determinism)
    def tie_breaker_key(item: Dict[str, Any]) -> Tuple[float, int, int, int, str]:
        score = item["relevance_score"]
        is_active = 1 if item.get("discontinued") == "N" else 0
        is_aggregate = 1 if item.get("airport") == "Metro Airports" or not item.get("parent") else 0
        # If item has a child order in hierarchy
        child_order = item.get("child_order", 999)
        ident = item.get("identifier", "")
        # Sort by: -score, -is_active, -is_aggregate, child_order, ident
        return (-score, -is_active, -is_aggregate, child_order, ident)

    scored_records.sort(key=tie_breaker_key)

    return scored_records[:k]
