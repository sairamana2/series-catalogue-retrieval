"""Configuration and domain entity definitions for Time Series Catalogue Retrieval."""

from pathlib import Path
from typing import Dict, List, Set

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_PATH = BASE_DIR / "series_catalogue_raw.csv"
DEFAULT_DB_PATH = BASE_DIR / "catalogue.db"
DEFAULT_VECTORS_PATH = BASE_DIR / "vectors.npy"
DEFAULT_VECTOR_IDS_PATH = BASE_DIR / "vector_ids.json"

# Embedding Model Configuration
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384

# Scoring & Ranking Parameters
LEXICAL_WEIGHT = 0.45
VECTOR_WEIGHT = 0.35
CONSTRAINT_BOOST_STRONG = 2.5
CONSTRAINT_BOOST_MEDIUM = 1.5
CONFLICT_PENALTY = 3.0
DISCONTINUED_PENALTY = 1.2
RELEVANCE_SCORE_THRESHOLD = 0.18

# Domain Entity Aliases & Synonyms
AIRPORT_ALIASES: Dict[str, str] = {
    "bangalore": "Banglore",
    "banglore": "Banglore",
    "bengaluru": "Banglore",
    "blr": "Banglore",
    "delhi": "Delhi",
    "new delhi": "Delhi",
    "del": "Delhi",
    "mumbai": "Mumbai",
    "bombay": "Mumbai",
    "bom": "Mumbai",
    "chennai": "Chennai",
    "madras": "Chennai",
    "maa": "Chennai",
    "kolkata": "Kolkata",
    "calcutta": "Kolkata",
    "ccu": "Kolkata",
    "hyderabad": "Hyderabad",
    "hyd": "Hyderabad",
    "ahmedabad": "Ahmedabad",
    "amd": "Ahmedabad",
    "guwahati": "Guwahati",
    "gau": "Guwahati",
    "kochi": "Kochi",
    "cochin": "Kochi",
    "cok": "Kochi",
    "lucknow": "Lucknow",
    "lko": "Lucknow",
    "metro": "Metro Airports",
    "metro airports": "Metro Airports"
}

AIRLINE_ALIASES: Dict[str, str] = {
    "indigo": "Indigo",
    "interglobe": "Indigo",
    "go air": "Go Air",
    "goair": "Go Air",
    "go first": "Go Air",
    "g8": "Go Air",
    "vistara": "Vistara",
    "uk": "Vistara",
    "air india": "Air India",
    "ai": "Air India",
    "air asia": "Air Asia",
    "airasia": "Air Asia",
    "spicejet": "SpiceJet",
    "spice jet": "SpiceJet",
    "sg": "SpiceJet",
    "alliance air": "Alliance Air",
    "akasa air": "Akasa Air",
    "akasa": "Akasa Air",
    "aix connect": "AIX Connect",
    "aix": "AIX Connect",
    "air india express": "Air India Express"
}

CURRENCY_ALIASES: Dict[str, Dict[str, str]] = {
    "dollar": {"currency": "USD", "unit": "US Dollar"},
    "dollars": {"currency": "USD", "unit": "US Dollar"},
    "usd": {"currency": "USD", "unit": "US Dollar"},
    "$": {"currency": "USD", "unit": "US Dollar"},
    "us dollar": {"currency": "USD", "unit": "US Dollar"},
    "us dollars": {"currency": "USD", "unit": "US Dollar"},
    "rupee": {"currency": "INR", "unit": "Rupees"},
    "rupees": {"currency": "INR", "unit": "Rupees"},
    "inr": {"currency": "INR", "unit": "Rupees"},
    "rs": {"currency": "INR", "unit": "Rupees"},
    "₹": {"currency": "INR", "unit": "Rupees"}
}

FREQUENCY_ALIASES: Dict[str, str] = {
    "monthly": "Monthly",
    "month": "Monthly",
    "daily": "Daily",
    "day": "Daily"
}

FLOW_ALIASES: Dict[str, str] = {
    "export": "Exports",
    "exports": "Exports",
    "import": "Imports",
    "imports": "Imports",
    "trade balance": "Trade Balance",
    "balance of trade": "Trade Balance",
    "balance": "Trade Balance"
}

METRIC_SYNONYMS: Dict[str, str] = {
    "punctuality": "on time performance",
    "punctual": "on time performance",
    "on-time": "on time performance",
    "on-time performance": "on time performance",
    "otp": "on time performance",
    "delays": "on time performance",
    "delay": "on time performance",
    "flights": "flight airline aviation on time performance",
    "flight": "flight airline aviation on time performance"
}

CALC_TYPE_ALIASES: Dict[str, str] = {
    "cumulative": "Cumulative",
    "ytd": "Cumulative",
    "monthly": "Monthly"
}

# Known Commodities extracted from Merchandise Trade
KNOWN_COMMODITIES: Set[str] = {
    "Cashew", "Carpets", "Ceramic products & glassware",
    "Cereal preparations & Miscellaneous processed items", "Chemical material & products",
    "Coal, Coke & Briquettes, etc.", "Coffee", "Cotton Raw & Waste",
    "Cotton Yarn/Fabs./made-ups, Handloom Products etc.", "Drugs & Pharmaceuticals",
    "Dyeing/tanning/colouring materials", "Electronic Goods", "Engineering Goods",
    "Fertilisers, Crude & manufactured", "Fruits & Vegetables", "Gems & Jewellery",
    "Gold", "Handicrafts excluding hand made carpet", "Iron & Steel", "Iron Ore",
    "Jute Mfg. including Floor Covering", "Leather & leather products",
    "Man-made Yarn/Fabs./made-ups etc.", "Marine Products", "Meat, dairy & poultry products",
    "Mica, Coal & Other Ores, Minerals including processed minerals", "Non-ferrous metals",
    "Oil Meals", "Oil seeds", "Organic & Inorganic Chemicals", "Other commodities",
    "Other plastic items", "Petroleum Products", "Petroleum, Crude & products",
    "Plastic & Linoleum", "Project goods", "Pulses", "Rice", "Silver", "Spices",
    "Tea", "Textile yarn Fabric, made-up articles", "Tobacco", "Total",
    "Transport Equipment", "Vegetable Oil", "Wood & Wood products"
}
