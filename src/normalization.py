"""Entity extraction, text cleaning, and query normalization."""

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from config import (
    AIRLINE_ALIASES,
    AIRPORT_ALIASES,
    CALC_TYPE_ALIASES,
    CURRENCY_ALIASES,
    FLOW_ALIASES,
    FREQUENCY_ALIASES,
    KNOWN_COMMODITIES,
    METRIC_SYNONYMS,
)


def clean_text(text: Optional[str]) -> str:
    """Normalize whitespace, remove embedded newlines, and strip text."""
    if not text:
        return ""
    # Replace newlines and carriage returns with space
    cleaned = text.replace("\r", " ").replace("\n", " ")
    # Collapse multiple whitespace characters
    return re.sub(r"\s+", " ", cleaned).strip()


def extract_record_entities(raw_record: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Extract structured dimensions from title and metadata of a catalogue record."""
    clean_title = clean_text(raw_record.get("Title", ""))
    category = raw_record.get("Category", "")
    subcategory = raw_record.get("SubCategory", "")

    airline: Optional[str] = None
    airport: Optional[str] = None
    commodity: Optional[str] = None
    flow: Optional[str] = None
    calc_type: Optional[str] = None

    if category == "Civil Aviation":
        # Extract Airport
        match_airport = re.search(r"at (.*?) airport", clean_title, re.IGNORECASE)
        if match_airport:
            raw_airport = match_airport.group(1).strip()
            airport = AIRPORT_ALIASES.get(raw_airport.lower(), raw_airport)
        elif "Metro Airports" in clean_title:
            airport = "Metro Airports"

        # Extract Airline
        for alias, canonical in AIRLINE_ALIASES.items():
            pattern = r"\b" + re.escape(alias) + r"\b"
            if re.search(pattern, clean_title, re.IGNORECASE):
                airline = canonical
                break

    elif category == "Foreign Trade":
        # Extract Trade Flow
        for alias, canonical in FLOW_ALIASES.items():
            pattern = r"\b" + re.escape(alias) + r"\b"
            if re.search(pattern, clean_title, re.IGNORECASE):
                flow = canonical
                break

        # Extract Commodity
        match_comm = re.search(r"Merchandise (?:Exports|Imports) - (.*?)\s*\(", clean_title)
        if match_comm:
            commodity = match_comm.group(1).strip()
        elif "Trade Balance" in clean_title:
            commodity = "Trade Balance"
        elif "Total" in clean_title:
            commodity = "Total"

        # Extract Calculation Type
        if "Cumulative" in clean_title:
            calc_type = "Cumulative"
        elif "Monthly" in clean_title:
            calc_type = "Monthly"

    return {
        "airline": airline,
        "airport": airport,
        "commodity": commodity,
        "flow": flow,
        "calc_type": calc_type,
    }


def build_search_tokens(
    identifier: str,
    clean_title: str,
    category: str,
    subcategory: str,
    subset: str,
    frequency: str,
    unit: str,
    currency: str,
    entities: Dict[str, Optional[str]],
) -> str:
    """Build rich denormalized search text containing all tokens and expanded aliases."""
    tokens: List[str] = [
        identifier,
        clean_title,
        category,
        subcategory,
        subset,
        frequency,
        unit,
        currency,
    ]

    airline = entities.get("airline")
    airport = entities.get("airport")
    commodity = entities.get("commodity")
    flow = entities.get("flow")
    calc_type = entities.get("calc_type")

    if airline:
        tokens.append(airline)
        if airline.lower() == "indigo":
            tokens.extend(["IndiGo", "6E", "InterGlobe"])
        elif airline.lower() == "spicejet":
            tokens.extend(["Spice Jet", "SpiceJet"])
    if airport:
        tokens.append(airport)
        if airport.lower() == "banglore":
            tokens.extend(["Bangalore", "Bengaluru", "BLR"])
        elif airport.lower() == "delhi":
            tokens.extend(["DEL", "New Delhi", "Indira Gandhi"])
        elif airport.lower() == "mumbai":
            tokens.extend(["BOM", "Bombay"])
        elif airport.lower() == "chennai":
            tokens.extend(["MAA", "Madras"])

    if commodity:
        tokens.append(commodity)
    if flow:
        tokens.append(flow)
    if calc_type:
        tokens.append(calc_type)

    if currency == "USD":
        tokens.extend(["dollar", "dollars", "USD", "$", "US Dollar"])
    elif currency == "INR":
        tokens.extend(["rupee", "rupees", "INR", "Rs", "₹"])

    if category == "Civil Aviation":
        tokens.extend(["punctuality", "punctual", "on-time", "on time performance", "OTP", "flight", "flights", "aviation"])

    # Remove duplicates preserving order
    seen: Set[str] = set()
    unique_tokens: List[str] = []
    for token in tokens:
        cleaned = clean_text(token)
        if cleaned and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            unique_tokens.append(cleaned)

    return " ".join(unique_tokens)


def parse_query_intent(query: str) -> Dict[str, Any]:
    """Parse user query into normalized entities, constraints, and search terms."""
    q_norm = clean_text(query).lower()

    airline: Optional[str] = None
    airport: Optional[str] = None
    commodity: Optional[str] = None
    flow: Optional[str] = None
    calc_type: Optional[str] = None
    frequency: Optional[str] = None
    currency: Optional[str] = None
    unit: Optional[str] = None
    has_cargo_term: bool = False
    is_punctuality_query: bool = False

    # Check for cargo terms (Case 5 negative constraint)
    if any(k in q_norm for k in ["cargo", "tonnage", "freight"]):
        has_cargo_term = True

    # Check for punctuality synonyms
    for p_term in ["punctuality", "punctual", "on-time", "on time", "otp", "delay", "delays"]:
        if p_term in q_norm:
            is_punctuality_query = True
            break

    # Airline extraction
    for alias, canonical in AIRLINE_ALIASES.items():
        pattern = r"\b" + re.escape(alias) + r"\b"
        if re.search(pattern, q_norm):
            airline = canonical
            break

    # Airport extraction
    for alias, canonical in AIRPORT_ALIASES.items():
        pattern = r"\b" + re.escape(alias) + r"\b"
        if re.search(pattern, q_norm):
            airport = canonical
            break

    # Frequency extraction
    for alias, canonical in FREQUENCY_ALIASES.items():
        pattern = r"\b" + re.escape(alias) + r"\b"
        if re.search(pattern, q_norm):
            frequency = canonical
            break

    # Calculation type extraction
    for alias, canonical in CALC_TYPE_ALIASES.items():
        pattern = r"\b" + re.escape(alias) + r"\b"
        if re.search(pattern, q_norm):
            calc_type = canonical
            break

    # Currency extraction
    for alias, curr_dict in CURRENCY_ALIASES.items():
        pattern = r"\b" + re.escape(alias) + r"\b"
        if re.search(pattern, q_norm):
            currency = curr_dict["currency"]
            unit = curr_dict["unit"]
            break

    # Flow extraction
    for alias, canonical in FLOW_ALIASES.items():
        pattern = r"\b" + re.escape(alias) + r"\b"
        if re.search(pattern, q_norm):
            flow = canonical
            break

    # Commodity extraction
    for comm in KNOWN_COMMODITIES:
        pattern = r"\b" + re.escape(comm.lower()) + r"\b"
        if re.search(pattern, q_norm):
            commodity = comm
            break

    return {
        "raw_query": query,
        "clean_query": clean_text(query),
        "airline": airline,
        "airport": airport,
        "commodity": commodity,
        "flow": flow,
        "calc_type": calc_type,
        "frequency": frequency,
        "currency": currency,
        "unit": unit,
        "has_cargo_term": has_cargo_term,
        "is_punctuality_query": is_punctuality_query,
    }
