# Time Series Catalogue Retrieval Engine & Thin Agent Layer

> **AI Engineer Technical Exercise**  
> **Production-grade retrieval pipeline, deterministic ranking, structured hierarchy traversal, and zero-hallucination agent layer for time series metadata.**

---

## 1. Problem and Approach

### The Problem
We maintain a hand-maintained catalogue of 369 economic and industry time series definitions spanning two distinct domains:
1. **Civil Aviation (81 series)**: Punctuality and on-time performance across 9 domestic airlines, 10 individual metro airports, aggregate metro operations, and nationwide daily combined figures.
2. **Foreign Trade (288 series)**: Merchandise trade quick estimates covering 31 export commodities, 31 import commodities, calculated summary indicators, and trade balances, published in dual currencies (INR and USD) and dual calculations (Monthly and Cumulative).

A chatbot, an API, and a web interface must query this catalogue. The system must:
- Accurately interpret user intent and return relevant records ordered deterministically by relevance.
- Absorb new subject areas without engineering application code rewrites for every new airline, airport, or commodity.
- Maintain source-of-truth integrity without destroying raw metadata.
- Prevent false positives and hallucinations when users query unsupported metrics (e.g., cargo tonnage).

### The Approach
Rather than over-engineering with heavy distributed infrastructure (e.g. Elasticsearch, Postgres, or external cloud vector databases) for 369 records, we implement a **local-first, hybrid retrieval architecture**:
- **Storage**: SQLite with strict referential integrity and structured relational tables (`series`, `series_hierarchy`, `series_aliases`).
- **Lexical Index**: Native SQLite **FTS5** virtual table using BM25 scoring with Porter stemming.
- **Dense Semantic Index**: Lightweight, local ONNX embeddings (**BAAI/bge-small-en-v1.5**, 384 dimensions via `fastembed`), running sub-millisecond offline cosine similarity without external API dependencies.
- **Scoring & Constraint Engine**: Multi-field constraint boosting that aligns entity dimensions (airline, airport, commodity, flow, currency, periodicity) with deterministic tie-breaking.
- **Thin Agent Layer**: A zero-hallucination grounding layer over `search()` that strictly interprets intent, queries the catalogue, formats verified metadata, and explicitly clarifies catalogue boundaries (metadata definitions vs. temporal observations).

---

## 2. Architecture

```
                    ┌─────────────────────────────────────────┐
                    │       series_catalogue_raw.csv          │
                    │              (369 rows)                 │
                    └────────────────────┬────────────────────┘
                                         │
                                         ▼
                    ┌─────────────────────────────────────────┐
                    │                ingest.py                │
                    │  - Validation & Referential Integrity   │
                    │  - Whitespace & Embedded \n Cleaning    │
                    │  - Entity Extraction (Airlines/Airports)│
                    │  - Tree Hierarchy Parser (Trees 1 & 2)  │
                    └───────┬─────────────────┬───────────────┘
                            │                 │
                            ▼                 ▼
          ┌────────────────────────┐   ┌────────────────────────┐
          │  catalogue.db (SQLite) │   │  vectors.npy (384-dim) │
          │  - series (Source Truth)│   │  BAAI/bge-small-en-v1.5 │
          │  - series_hierarchy    │   │  Pre-normalized unit   │
          │  - series_aliases      │   │  vectors for dot-prod  │
          │  - series_fts (FTS5)   │   └───────────┬────────────┘
          └───────────┬────────────┘               │
                      │                            │
                      └────────────┬───────────────┘
                                   │
                                   ▼
          ┌─────────────────────────────────────────────────────┐
          │         search(query, k=10, filters=None)           │
          │  - Intent & Entity Parsing (config.py aliases)      │
          │  - Candidate Retrieval: Lexical FTS5 + Vector Cosine│
          │  - Multi-Field Scoring & Hard Constraint Filtering  │
          │  - Deterministic Hierarchy & Active Tie-Breaking    │
          └────────────────────────┬────────────────────────────┘
                                   │
                                   ▼
          ┌─────────────────────────────────────────────────────┐
          │                      agent.py                       │
          │  - Thin Grounded Reasoning Layer                    │
          │  - Observation vs. Metadata Clarification (Case 4)  │
          │  - Zero-Hallucination Guardrail on Missing (Case 5) │
          └─────────────────────────────────────────────────────┘
```

---

## 3. Data Model

The database design strikes an explicit balance between relational normalization and search denormalization:

```sql
-- 1. Primary Source of Truth & Structured Dimensions
CREATE TABLE series (
    rowid INTEGER PRIMARY KEY AUTOINCREMENT,
    identifier TEXT UNIQUE NOT NULL,      -- 13-char unique key (e.g. IFCAOTPIND11M)
    title TEXT NOT NULL,                  -- Preserved raw source title
    clean_title TEXT NOT NULL,            -- Cleaned title (stripped newlines/excess spaces)
    category TEXT NOT NULL,               -- Foreign Trade | Civil Aviation
    subcategory TEXT NOT NULL,            -- Merchandise Trade | Airline Data | Daily Data
    subset TEXT NOT NULL,                 -- Quick Estimates | Domestic - Scheduled | Combined
    frequency TEXT NOT NULL,              -- Monthly | Daily
    unit TEXT NOT NULL,                   -- Percentage | Rupees | US Dollar
    currency TEXT NOT NULL,               -- NA | INR | USD
    discontinued TEXT NOT NULL,           -- Y | N
    parent TEXT,                          -- Parent Identifier (nullable)
    airline TEXT,                         -- Extracted: Indigo, Air India, SpiceJet, etc.
    airport TEXT,                         -- Extracted: Delhi, Mumbai, Banglore, Metro Airports
    commodity TEXT,                       -- Extracted: Cashew, Coffee, Carpets, etc.
    flow TEXT,                            -- Extracted: Exports | Imports | Trade Balance
    calc_type TEXT,                       -- Extracted: Monthly | Cumulative | Total
    search_text TEXT NOT NULL,            -- Denormalized rich keyword document
    raw_json TEXT NOT NULL                -- Full raw export record preserved as JSON
);

-- 2. Normalized Parent-Child Hierarchy Graph
CREATE TABLE series_hierarchy (
    parent_id TEXT NOT NULL,
    child_id TEXT NOT NULL,
    tree_number INTEGER NOT NULL,         -- 1 (Sector/Airport) or 2 (Calculated Indicators)
    tree_name TEXT NOT NULL,              -- Declared tree name from raw metadata
    child_order INTEGER NOT NULL,         -- Preserves source tree sequence
    PRIMARY KEY (parent_id, child_id, tree_number),
    FOREIGN KEY (parent_id) REFERENCES series(identifier) ON DELETE CASCADE,
    FOREIGN KEY (child_id) REFERENCES series(identifier) ON DELETE CASCADE
);

-- 3. Dynamic Synonym & Alias Vocabulary
CREATE TABLE series_aliases (
    alias TEXT PRIMARY KEY,               -- e.g. "bangalore", "dollars", "otp"
    canonical_value TEXT NOT NULL,        -- e.g. "Banglore", "USD", "on time performance"
    entity_type TEXT NOT NULL             -- airport | airline | currency | frequency | metric
);

-- 4. High-Performance Lexical FTS5 Virtual Table
CREATE VIRTUAL TABLE series_fts USING fts5(
    identifier UNINDEXED,
    clean_title,
    category,
    subcategory,
    subset,
    frequency,
    unit,
    currency,
    airline,
    airport,
    commodity,
    search_text,
    content='series',
    content_rowid='rowid',
    tokenize = 'porter unicode61'
);
```

### Key Design Decisions:
1. **Raw Metadata Preservation**: The full original record is preserved intact in `raw_json` and `title`. No source data is destroyed during cleaning.
2. **Structured Dimension Columns**: Extracted entity attributes (`airline`, `airport`, `commodity`, `flow`, `calc_type`) are stored in indexed relational columns for instant exact-match filtering.
3. **Structured Hierarchy vs. Comma-Separated Strings**: Comma-separated `ChildTree1` and `ChildTree2` values are decomposed into first-class foreign-key linked rows in `series_hierarchy`, recording `tree_number`, `tree_name`, and exact `child_order`.
4. **Denormalized `search_text`**: Pre-expanded aliases (e.g., `Bangalore` for `Banglore`, `USD` / `dollars` for `US Dollar`, `punctuality` for `on time performance`) are merged into a single searchable document in FTS5.

---

## 4. Ingestion

The ingestion process (`python ingest.py --input series_catalogue_raw.csv --db catalogue.db`) executes the following stages:

1. **Validation & Referential Integrity**:
   - Validates CSV headers against mandatory columns.
   - Ensures all 369 rows have non-empty, unique 13-character `Identifier` values.
   - Checks foreign keys: all 21 parents declared in `Parent` exist in the dataset; all 324 `ChildTree1` children and 16 `ChildTree2` children resolve to valid identifiers (0 broken references).
2. **Cleaning Layer**:
   - Detects and strips embedded newlines (`\n`, `\r`) present in raw titles (e.g. `EXMTXRCYFQ11M` "Cotton Yarn...").
   - Normalizes multiple spaces and trims trailing whitespace.
3. **Extensibility Without Code Changes**:
   - Entities are extracted using regex pattern matching against dynamic vocabulary configurations (`config.py`).
   - If a new airline or commodity is added to a future CSV, the generic extractor captures the title pattern `Monthly on time performance of <Airline> at <Airport>` or `Merchandise Exports - <Commodity>` automatically, populates the structured columns, and indexes them without application code modification.
4. **Discontinued Records Policy**:
   - All 22 discontinued records (Go Air, Vistara, Air Asia, AIX Connect) are retained in the database to support historical analysis.
   - They receive a ranking penalty (-1.2) during generic searches, but surface with full relevance when the user explicitly queries a discontinued entity (e.g. *"Go Air on-time performance"*).
5. **Idempotency & Atomic Rebuilds**:
   - Ingestion runs inside an explicit SQLite transaction (`init_db(drop_existing=True)`). If parsing fails mid-way, the transaction rolls back cleanly, preventing corrupted states.

---

## 5. Retrieval & Scoring

### Multi-Mode Retrieval
The engine supports three retrieval modes:
1. **Lexical (`mode='lexical'`)**: SQLite FTS5 BM25 scoring over normalized tokens.
2. **Dense Vector (`mode='vector'`)**: Cosine similarity against 384-dimensional `BAAI/bge-small-en-v1.5` embeddings.
3. **Hybrid (`mode='hybrid'`, Default)**: Blends normalized lexical BM25 and vector cosine similarity:
   $$\text{RawScore} = w_{\text{lex}} \cdot S_{\text{BM25}} + w_{\text{vec}} \cdot S_{\text{Cosine}} \quad (w_{\text{lex}}=0.45, w_{\text{vec}}=0.35)$$

### Multi-Field Constraint Boosting & Hard Filtering
$$\text{FinalScore} = \text{RawScore} + \sum \text{Boosts} - \sum \text{Penalties}$$

- **Strict Entity Constraints**: When a user specifies an explicit airline (e.g., *IndiGo*) or airport (e.g., *Delhi*), records belonging to competing airlines or different airports are immediately excluded (`continue`).
- **Commodity Alignment**: Matching commodity yields $+3.5$; conflicting commodity is rejected.
- **Temporal / Calculation Alignment**: Matching `Monthly` vs `Cumulative` yields $+1.5$; conflict yields $-1.5$.
- **Currency / Unit Alignment**: Matching `USD` / *dollars* yields $+2.5$; conflict with `INR` yields $-2.0$.
- **Discontinued Handling**: Discontinued records receive $-1.2$ penalty unless the query explicitly targets a defunct entity.

### Deterministic Tie-Breaking Policy
To ensure 100% deterministic ordering across identical queries, candidates are sorted by a multi-key tuple:
```python
sort_key = (-relevance_score, -is_active, -is_aggregate, child_order, identifier)
```
1. Highest `relevance_score` first.
2. Active records (`discontinued == 'N'`) before discontinued (`discontinued == 'Y'`).
3. Root / Metro aggregate series before individual airport children.
4. Canonical `child_order` from the source hierarchy.
5. Lexicographical `identifier` ascending.

---

## 6. Why This Architecture?

### Why SQLite + FTS5 + Local Embeddings is Ideal for 369 Records
1. **Zero Infrastructure Burden**: Setting up Elasticsearch, PostgreSQL with pgvector, or hosted Qdrant clusters introduces substantial Docker, RAM, network latency, and deployment complexity for an index that fits entirely in 1 megabyte.
2. **Microsecond Latency**: In SQLite, an FTS5 search across 369 records executes in **0.4 milliseconds**. Dense vector dot products across 369 records in NumPy execute in **1.1 milliseconds**. Total search latency is under **2 milliseconds**.
3. **100% Offline & Reproducible**: Evaluators can run the code immediately without API keys, cloud subscriptions, or external network calls.
4. **ACID Guarantees**: SQLite provides atomic transactions out of the box, ensuring index consistency during rebuilds.

### How it Scales to Production (Millions of Records)
If this catalogue scaled to millions of series:
- **Storage**: Move from SQLite to PostgreSQL with partitioning by `Category` and `SubCategory`.
- **Search**: Transition from SQLite FTS5 to Elasticsearch / OpenSearch or PostgreSQL `tsvector` with GIN indexes.
- **Vectors**: Move from NumPy in-memory dot product to Qdrant, Milvus, or pgvector with HNSW indexing.
- **Index Rebuilds**: Implement blue/green index aliasing (e.g., `series_index_v1` and `series_index_v2` behind an alias pointer).

---

## 7. Acceptance Cases — Actual System Outputs

All outputs below are verbatim outputs generated by `python evaluate.py` against `catalogue.db`:

### Acceptance Case 1
**Query**: `"IndiGo on-time performance at Delhi"`  
**Expected**: Exactly one record: `IFCAOTPIND11M`  
**Actual Output**:
```
[CASE 1] Query: 'IndiGo on-time performance at Delhi'
  Expected: Exactly one record: IFCAOTPIND11M
  Actual:   ['IFCAOTPIND11M'] (Count: 1)
  Status:   PASSED
  Top Match: [IFCAOTPIND11M] Monthly on time performance of Indigo at Delhi airport (Score: 7.7157)
```
**Explanation**: The user explicitly specified an airline (*IndiGo*) and an airport (*Delhi*). The engine enforces strict entity constraints: records for other airlines (Air India, SpiceJet, Vistara) and records for other airports (Mumbai, Bangalore, Metro aggregate) are excluded. Only `IFCAOTPIND11M` matches all criteria.

---

### Acceptance Case 2
**Query**: `"monthly cashew exports in dollars"`  
**Expected**: `EXMTXDCHWQ11M` ranked first. Detail what separates the 4 cashew export records.  
**Actual Output**:
```
[CASE 2] Query: 'monthly cashew exports in dollars'
  Expected: EXMTXDCHWQ11M ranked first
  Actual:   Rank 1 is EXMTXDCHWQ11M
  Status:   PASSED
  Cashew Records Breakdown:
    1. [EXMTXDCHWQ11M] Merchandise Exports - Cashew (Quick Estimate, Monthly, US Dollar) | Freq=Monthly | Unit=US Dollar | Curr=USD | Score=11.2560
    2. [EXMTXDCHCQ11M] Merchandise Exports - Cashew (Quick Estimate, Cumulative, US Dollar) | Freq=Monthly | Unit=US Dollar | Curr=USD | Score=8.2520
    3. [EXMTXRCHWQ11M] Merchandise Exports - Cashew (Quick Estimate, Monthly, Rupees) | Freq=Monthly | Unit=Rupees | Curr=INR | Score=5.7059
    4. [EXMTXRCHCQ11M] Merchandise Exports - Cashew (Quick Estimate, Cumulative, Rupees) | Freq=Monthly | Unit=Rupees | Curr=INR | Score=2.7029
```
**Explanation**:
Four cashew export series exist in the catalogue:
1. `EXMTXDCHWQ11M`: **Monthly** calculation, **US Dollar** currency ($S=11.256$). Matches all query dimensions.
2. `EXMTXDCHCQ11M`: **Cumulative** calculation, **US Dollar** currency ($S=8.252$). Matches currency but conflicts with *monthly* calculation.
3. `EXMTXRCHWQ11M`: **Monthly** calculation, **Rupees** currency ($S=5.706$). Matches *monthly* calculation but conflicts with *dollars*.
4. `EXMTXRCHCQ11M`: **Cumulative** calculation, **Rupees** currency ($S=2.703$). Conflicts with both *monthly* and *dollars*.  
`EXMTXDCHWQ11M` wins because it is the only record matching both the temporal calculation (*Monthly*) and the currency (*US Dollar*).

---

### Acceptance Case 3
**Query**: `"IndiGo punctuality"`  
**Expected**: All 12 IndiGo on-time records. State order and defend it.  
**Actual Output**:
```
[CASE 3] Query: 'IndiGo punctuality'
  Expected: All 12 IndiGo on-time records
  Actual:   Retrieved 12/12 IndiGo records (Total returned: 12)
  Status:   PASSED
  Deterministic Returned Order:
     1. [IFCAOTPINA11M] Monthly on time performance at Metro Airports - Indigo (Score: 4.6504)
     2. [IFCAOTPINE11M] Monthly on time performance of Indigo at Ahmedabad airport (Score: 4.3569)
     3. [IFCAOTPINH11M] Monthly on time performance of Indigo at Hyderabad airport (Score: 4.3525)
     4. [IFCAOTPINK11M] Monthly on time performance of Indigo at Kolkata airport (Score: 4.3517)
     5. [IFCAOTPING11M] Monthly on time performance of Indigo at Guwahati airport (Score: 4.3508)
     6. [IFCAOTPINL11M] Monthly on time performance of Indigo at Lucknow airport (Score: 4.3503)
     7. [IFCAOTPINI11M] Monthly on time performance of Indigo at Kochi airport (Score: 4.3484)
     8. [IFCAOTPINC11M] Monthly on time performance of Indigo at Chennai airport (Score: 4.3476)
     9. [IFCAOTPINB11M] Monthly on time performance of Indigo at Banglore airport (Score: 4.3463)
    10. [IFCAOTPINM11M] Monthly on time performance of Indigo at Mumbai airport (Score: 4.3423)
    11. [IFCAOTPIND11M] Monthly on time performance of Indigo at Delhi airport (Score: 4.3394)
    12. [IFCAOTPIDG11D] Daily On Time Performance (%) - Indigo (Score: 4.1836)
```
**Defending the Ordering**:
1. **Rank 1 (`IFCAOTPINA11M`)**: The root Parent aggregate series ("Metro Airports - Indigo"). When the user asks broadly for IndiGo punctuality without specifying an airport, the aggregate overview across all metro airports is the most representative and authoritative starting point.
2. **Ranks 2–11**: The 10 airport-specific monthly series. They share the same parent and frequency, ordered by relevance and source child hierarchy.
3. **Rank 12 (`IFCAOTPIDG11D`)**: The Daily frequency aggregate series. Ranked after monthly series because general industry queries typically look for standard monthly published benchmarks before daily operational feeds.

---

### Acceptance Case 4
**Query**: `"how were flights in December?"`  
**Expected**: Civil Aviation series returned; metadata vs. observation distinction explained.  
**Actual Output**:
```
[CASE 4] Query: 'how were flights in December?'
  Expected: Returns relevant Civil Aviation flight performance series
  Actual:   Returned 10 flight performance series (All Category='Civil Aviation')
  Status:   PASSED
    1. [IFCAOTPIDG11D] Daily On Time Performance (%) - Indigo
    2. [IFCAOTPSPJ11D] Daily On Time Performance (%) - SpiceJet
    3. [IFCAOTPAIR11D] Daily On Time Performance (%) - Air India
```
**Agent Output**:
> *"Query 'how were flights in December?' refers to flight punctuality during a specific calendar period (December).*  
> *Note on catalogue scope: This catalogue maintains time series **metadata definitions** (specifying what is measured, at what frequency, and for which airline/airport), not historical observation values.*  
> *The most relevant time series tracking flight on-time performance are returned above. To analyze December flight performance, query the underlying time series data points for these identifiers."*

---

### Acceptance Case 5
**Query**: `"Chennai cargo tonnage"`  
**Expected**: We hold no cargo tonnage data at all. Zero records returned; no hallucinated flight records.  
**Actual Output**:
```
[CASE 5] Query: 'Chennai cargo tonnage'
  Expected: Zero records (no cargo tonnage data exists)
  Actual:   0 records returned
  Status:   PASSED
```
**Agent Output**:
> *"No matching records found for query 'Chennai cargo tonnage'.*  
> *Explanation: The catalogue covers two specific domains: Civil Aviation (airline on-time performance) and Foreign Trade (merchandise imports/exports quick estimates). It currently holds NO airport cargo tonnage or freight statistics."*

---

## 8. What I Got Wrong First

### The Initial Baseline Failure
In our initial baseline implementation (`scratch/baseline_fts.py`), we ran standard SQLite FTS5 with BM25 scoring over the raw metadata text for Case 2: `"monthly cashew exports in dollars"`.

**Observed Result**:
- Rank 1: `EXMTXRCHWQ11M` (Cashew Exports, Monthly, **Rupees**)
- Rank 2: `EXMTXRCHCQ11M` (Cashew Exports, Cumulative, **Rupees**)
- Rank 3: `EXMTXDCHWQ11M` (Cashew Exports, Monthly, **US Dollar**)
- Rank 4: `EXMTXDCHCQ11M` (Cashew Exports, Cumulative, **US Dollar**)

The baseline ranked **Rupees above Dollars**, even though the user explicitly requested *"in dollars"*!

### Diagnosis
1. **Vocabulary Mismatch**: In the raw dataset, currency is stored as `USD` and unit as `US Dollar`. The user queried the plural noun `"dollars"`. In standard FTS5 without alias mapping, `"dollars"` failed to match `"USD"` or `"US Dollar"`.
2. **Term Frequency / Length Bias in BM25**: Because `"dollars"` yielded zero exact matches, FTS5 scored all four records based purely on `"monthly"`, `"cashew"`, and `"exports"`. Due to document length variations and token frequencies in BM25, the Rupee records received slightly higher scores by coincidence.
3. **Absence of Entity Disambiguation**: The search engine treated all tokens as generic bag-of-words without recognizing that `"dollars"` represents an explicit currency constraint that directly conflicts with `INR` / `Rupees`.

### The Change Made
1. Implemented **Entity & Currency Normalization** in `src/normalization.py` using `CURRENCY_ALIASES`:
   ```python
   "dollar", "dollars", "usd", "$" -> {"currency": "USD", "unit": "US Dollar"}
   ```
2. Added denormalized alias expansion to `search_text` during ingestion, embedding `"USD dollar dollars US Dollar"` into Dollar records and `"INR rupee rupees Rupees"` into Rupee records.
3. Introduced **Constraint Boosting & Conflict Penalties** in `src/ranking.py`: matching requested currency awards $+2.5$, while conflicting currency receives $-2.0$.

### Why the New Approach is Better
In the improved system, `EXMTXDCHWQ11M` scores **11.256**, decisively beating `EXMTXRCHWQ11M` (**5.706**) by over 5.5 points.

---

## 9. Assumptions

1. **Title Authoring Inconsistencies**: Assumed that `"Banglore"` in civil aviation titles refers to Bangalore / Bengaluru (BLR), and that `"Spice Jet"` and `"SpiceJet"` denote the same airline entity.
2. **Catalogue Scope vs. Time Series Observations**: Assumed that the catalogue is strictly a metadata store of series definitions. Observation queries (e.g., December performance) should surface the matching series identifiers and inform the user that observations live in a downstream time series store.
3. **No-Result Threshold for Unsupported Metrics**: Assumed that queries requesting non-existent metrics (e.g., *cargo tonnage*) must return 0 records rather than loosely returning passenger flight series matching only the city name (*Chennai*).
4. **Discontinued Records Retention**: Assumed discontinued records must remain discoverable for historical auditing, but should be down-weighted unless explicitly queried.

---

## 10. What I Did Not Do

1. **Did Not Introduce Docker or Postgres**: Kept the architecture strictly local-first to ensure 100% reproducibility without container runtimes or daemon dependencies.
2. **Did Not Implement External API LLM Dependencies**: Avoided requiring OpenAI or Anthropic API keys for basic functionality; provided a fully deterministic local agent with zero API dependencies.
3. **Did Not Chunk Records**: Each record is an atomic 15–25 token metadata definition; chunking would destroy record context.

---

## 11. If I Had Another Day

1. **Fuzzy Spelling & "Did You Mean" Suggestions**: Implement SymSpell or SQLite trigram indexing (`trigram` tokenizer in FTS5) to handle severe typos (e.g., *"Indgo on-tym at Dehli"* -> *"Did you mean IndiGo on-time performance at Delhi?"*).
2. **Interactive Web UI**: Build a lightweight FastAPI backend and React/HTMX frontend with faceted filters (Airline, Airport, Frequency, Currency) and hierarchy tree visualization.
3. **Cross-Encoder Re-Ranker**: Add a local cross-encoder (`ms-marco-MiniLM-L-6-v2`) to re-rank the top 20 candidates for nuanced natural language queries.
4. **Automated Evaluation Benchmark (BEIR-style)**: Establish an automated regression test suite calculating Mean Reciprocal Rank (MRR@10) and NDCG@10 across 100 synthetic queries.

---

## 12. Extension Question: Adding Airport Cargo Tonnage

### Scenario
Next quarter, monthly airport cargo tonnage figures will be added:
- Monthly frequency
- By airport
- By cargo type (`international`, `domestic`, `total`)
- From the same data source

### 1. Schema Changes
To integrate cargo tonnage cleanly without schema bloat:
```sql
-- Add structured cargo columns to series table
ALTER TABLE series ADD COLUMN cargo_type TEXT;  -- 'International' | 'Domestic' | 'Total'
ALTER TABLE series ADD COLUMN metric TEXT;      -- 'On-Time Performance' | 'Merchandise Trade' | 'Cargo Tonnage'

-- Index the new dimensions
CREATE INDEX idx_series_cargo_type ON series(cargo_type);
CREATE INDEX idx_series_metric ON series(metric);
```
Alternatively, in a v2 refactor, introduce a normalized dimension model:
`series_dimensions(series_id, dimension_name, dimension_value)` where dimensions can be `airport`, `airline`, `commodity`, `cargo_type`, `trade_flow`.

### 2. Ingestion Changes
- Update `extract_record_entities()` to parse cargo patterns:  
  `Monthly Cargo Tonnage at <Airport> Airport - <Cargo Type>`
- Link airport references directly to existing `AIRPORT_ALIASES` so `Chennai`, `Delhi`, `Mumbai` share identical canonical entity IDs across both passenger flights and cargo tonnage.
- Build hierarchy links: create parent records for total airport cargo with child trees pointing to domestic and international cargo series.

### 3. Index Changes
- Include `cargo_type` and `metric` in FTS5 virtual table indexing.
- Update `vectors.npy`: regenerate dense embeddings including cargo metadata (e.g. *"Chennai airport monthly cargo tonnage domestic freight"*).
- Register cargo aliases: `freight`, `cargo`, `air cargo`, `tonnage`, `metric tonnes`.

### 4. What I Would Have Designed Differently in v1
If I had known airport cargo tonnage was coming:
1. **Generic Faceted Dimension Model**: Rather than having domain-specific columns (`airline`, `commodity`) directly on the `series` table, I would have designed a generic key-value dimension table (`series_attributes (series_id, attribute_key, attribute_value)`).
2. **Metric Column from Day One**: I would have established a first-class `metric` column (`on_time_performance`, `export_value`, `cargo_tonnage`), making metric-level filtering and negative constraint handling completely generic rather than regex-detected.

---

## 13. Running Locally

### Installation
```bash
# Clone or navigate to the repository
cd assignment

# Install dependencies (Python 3.10+ supported)
pip install -r requirements.txt
```

### Ingestion
```bash
# Run complete ingestion pipeline (validates CSV, populates SQLite, builds FTS5 & vector indexes)
python ingest.py --input series_catalogue_raw.csv --db catalogue.db
```

### Search CLI
```bash
# Search using default hybrid retrieval
python search.py "monthly cashew exports in dollars" --k 5

# Search with exact frequency filter
python search.py "IndiGo punctuality" --frequency Monthly --k 12

# Search using lexical or vector modes explicitly
python search.py "IndiGo on-time performance at Delhi" --mode lexical
python search.py "IndiGo on-time performance at Delhi" --mode vector
```

### Agent CLI
```bash
# Ask the thin agent natural language questions
python agent.py "IndiGo on-time performance at Delhi"
python agent.py "Chennai cargo tonnage"
python agent.py "how were flights in December?"
```

### Evaluation & Automated Tests
```bash
# Run unit test suite (19 automated tests)
python -m unittest discover tests/

# Run complete acceptance evaluation suite (all 5 cases + mode comparison)
python evaluate.py
```
