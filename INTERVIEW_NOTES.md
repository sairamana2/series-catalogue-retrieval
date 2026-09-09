# Interview Preparation Notes: Defending Technical & Retrieval Decisions

> Concise, defensible answers to the 28 key technical questions likely to arise in a 30–45 minute technical interview.

---

### 1. Why SQLite?
**Answer**:
For 369 records, SQLite is the optimal engineering choice. It lives in-process, has zero network latency, requires zero external services or daemon management, provides ACID transactions for atomic index rebuilds, and includes native FTS5 full-text search in Python's standard library. It makes the entire project 100% reproducible on any machine with zero setup friction.

---

### 2. Why not Elasticsearch or PostgreSQL?
**Answer**:
Elasticsearch and PostgreSQL are exceptional tools for distributed systems with millions of documents, but using them for 369 records would be classic resume-driven development and over-engineering. They introduce Docker dependencies, socket connections, memory overhead, and operational complexity without improving retrieval quality on a 1MB dataset.

---

### 3. Why lexical retrieval (BM25)?
**Answer**:
Time series metadata queries frequently contain exact entity names, airport codes, currency units, and trade codes (e.g., "USD", "Delhi", "Cashew", "Monthly"). BM25 provides exact keyword precision and term frequency weighting that semantic embeddings often dilute.

---

### 4. Why vector retrieval?
**Answer**:
Users frequently use natural language synonyms that never appear literally in the raw CSV. For example, users query "punctuality", "flight delays", or "air travel", whereas the dataset strictly uses "on time performance" or "Airline Data". Dense embeddings map semantic synonyms to the same vector space.

---

### 5. Why hybrid retrieval?
**Answer**:
Neither lexical nor dense retrieval is sufficient alone. Lexical search fails on synonyms ("punctuality" vs "on time performance"), while dense embeddings struggle with exact constraint matching (often confusing "USD" and "Rupees" or "Monthly" and "Cumulative" because they appear in identical grammatical contexts). Hybrid blends the lexical precision of BM25 with the semantic recall of embeddings.

---

### 6. Why this embedding model (`BAAI/bge-small-en-v1.5`)?
**Answer**:
It is a top-tier embedding model for retrieval benchmarks (MTEB), has a compact 384-dimensional vector, runs locally on CPU using ONNX runtime via `fastembed`, and requires only ~60MB of disk space. It computes embeddings for all 369 records in seconds with zero GPU requirements and zero external API dependencies.

---

### 7. What exactly gets embedded?
**Answer**:
We embed a synthesized metadata document:
`"{clean_title} | {category} - {subcategory} | Frequency: {frequency} | Unit: {unit} | Currency: {currency}"`
Embedding title alone loses critical categorical boundaries, while dumping raw uncleaned text introduces noise from newlines and formatting.

---

### 8. Why one vector per record?
**Answer**:
Each catalogue record is an atomic, self-contained time series definition consisting of roughly 15 to 25 tokens. Chunking would fracture the relationship between the series title, unit, and frequency. One vector per record captures the exact holistic meaning of the series.

---

### 9. How does ranking work?
**Answer**:
Ranking uses a multi-stage formula:
$$\text{FinalScore} = (0.45 \cdot S_{\text{BM25}} + 0.35 \cdot S_{\text{Cosine}}) + \sum \text{Boosts} - \sum \text{Penalties}$$
It adds structured boosts for matching entities (airline, airport, commodity, currency, periodicity) and applies strict hard filtering when explicit contradictory entities are specified.

---

### 10. How are ties broken?
**Answer**:
Ties are broken deterministically using a multi-key tuple:
`(-relevance_score, -is_active, -is_aggregate, child_order, identifier)`.
This guarantees that identical queries produce identical results across runs, prioritizing active over discontinued records, aggregate root series over children, and sorting by canonical identifier order.

---

### 11. Why does the Delhi IndiGo query return exactly one result?
**Answer**:
The query specifies two mutually restrictive entity constraints: `airline="Indigo"` and `airport="Delhi"`. The ranking engine applies hard constraint filtering: candidates with competing airlines (Air India, SpiceJet) or other airports (Mumbai, Bangalore) are disqualified. In the entire catalogue of 369 records, only `IFCAOTPIND11M` satisfies both constraints.

---

### 12. Why does the cashew USD query rank `EXMTXDCHWQ11M` first?
**Answer**:
There are four cashew export records in the catalogue. All four match commodity ("Cashew") and flow ("Exports"). However:
- `EXMTXDCHWQ11M` matches **both** "Monthly" and "US Dollar" ($S=11.256$).
- `EXMTXDCHCQ11M` matches "US Dollar" but conflicts on "Cumulative" ($S=8.252$).
- `EXMTXRCHWQ11M` matches "Monthly" but conflicts on "Rupees" ($S=5.706$).
- `EXMTXRCHCQ11M` conflicts on both "Cumulative" and "Rupees" ($S=2.703$).
`EXMTXDCHWQ11M` is the only record satisfying both constraints.

---

### 13. Why this specific IndiGo ordering?
**Answer**:
When querying "IndiGo punctuality", all 12 IndiGo records match. The system orders them hierarchically:
1. **Rank 1 (`IFCAOTPINA11M`)**: The root Parent aggregate series ("Metro Airports - Indigo"), which is the authoritative overview series.
2. **Ranks 2–11**: The 10 individual airport monthly series, ordered by relevance and source child hierarchy order.
3. **Rank 12 (`IFCAOTPIDG11D`)**: The daily aggregate series, ordered after monthly benchmarks.

---

### 14. What happens for ambiguous queries?
**Answer**:
For broad queries (such as "flights in December"), the agent returns the top relevant series across airlines and explicitly explains that the catalogue contains time series *metadata definitions*, not historical data observations for specific months.

---

### 15. What happens when nothing matches?
**Answer**:
When an unsupported domain or metric is requested (such as "Chennai cargo tonnage"), the system returns **zero records** and the agent states clearly that no cargo tonnage data exists in the catalogue. It refuses to hallucinate flight on-time performance records just because "Chennai" appeared in the query.

---

### 16. Why retain discontinued records?
**Answer**:
Economic and industry analysts frequently perform historical backtesting and time series research on discontinued series (e.g. Go Air or Vistara). Deleting them would destroy historical lineage. Instead, we retain them in storage and apply a ranking penalty unless the query explicitly requests a discontinued entity.

---

### 17. How do you handle Bangalore / Banglore?
**Answer**:
In the raw data, titles use the archaic spelling "Banglore". We maintain a data-driven alias dictionary (`AIRPORT_ALIASES`) mapping "bangalore", "banglore", "bengaluru", and "blr" to the canonical representation. We also enrich the FTS5 `search_text` with alternate spellings during ingestion.

---

### 18. How are hierarchy fields represented?
**Answer**:
Rather than leaving comma-separated strings in `ChildTree1` and `ChildTree2`, ingestion normalizes them into a dedicated relational table `series_hierarchy (parent_id, child_id, tree_number, tree_name, child_order)` with foreign keys, enabling bidirectional graph traversal.

---

### 19. How is the index refreshed?
**Answer**:
The index is refreshed upon ingestion via `ingest.py`. It updates SQLite tables, rebuilds the FTS5 virtual table, and generates dense vector embeddings.

---

### 20. What happens during an index rebuild?
**Answer**:
In our SQLite implementation, ingestion runs inside a single atomic transaction. Readers see the previous consistent state until the transaction commits. If ingestion fails, the transaction rolls back cleanly. In production, we would use blue/green database swapping or index aliases.

---

### 21. How would this scale from 369 records to millions?
**Answer**:
1. Partition storage in PostgreSQL by domain category.
2. Replace SQLite FTS5 with Elasticsearch or PostgreSQL `tsvector` GIN indexes.
3. Replace NumPy dot products with an approximate nearest neighbor (ANN) vector database like Qdrant, Milvus, or pgvector using HNSW indexing.
4. Implement asynchronous background index rebuilding with blue/green alias pointers.

---

### 22. How would you evaluate retrieval quality in production?
**Answer**:
We would evaluate retrieval offline using an annotated test dataset measuring **MRR@10** (Mean Reciprocal Rank), **NDCG@10**, and **Precision@k**. In production, we would monitor online metrics such as Click-Through Rate (CTR) on top results, user refinement rate, and query reformulation frequency.

---

### 23. What is your guardrail metric?
**Answer**:
**False Positive Rate on Out-Of-Domain / Unsupported Queries (Zero-Result Precision)**. The search engine must return 0 results when a user asks for unsupported metrics (e.g. "Chennai cargo tonnage" or "crude oil production") rather than returning weakly related records.

---

### 24. How would you prove hybrid beats lexical in production?
**Answer**:
We would run an online A/B test routing 50% of user traffic to Lexical (BM25) and 50% to Hybrid. We would measure conversion to downstream visualization, query reformulation rate, and abandonment rate. A statistically significant drop in query reformulations would prove hybrid's superiority.

---

### 25. What did you get wrong initially?
**Answer**:
In our initial baseline, naive BM25 ranked Rupee cashew records above Dollar cashew records for "monthly cashew exports in dollars". Because "dollars" was plural and the catalogue used "USD" / "US Dollar", BM25 found zero matches for the currency token and scored solely on "cashew exports", where Rupee records happened to score slightly higher due to document length normalization. We fixed this by introducing currency alias expansion and constraint scoring.

---

### 26. What would you improve with another day?
**Answer**:
1. Implement fuzzy spelling correction (SymSpell / Trigram FTS5) to handle severe typos.
2. Add a local cross-encoder re-ranker (`ms-marco-MiniLM-L-6-v2`) for deep sentence-level query interaction.
3. Deploy an interactive FastAPI / React UI with visual hierarchy trees.

---

### 27. How would you add cargo tonnage?
**Answer**:
I would add structured columns (`cargo_type` and `metric`) to `series`, map airport names to our existing `AIRPORT_ALIASES`, parse parent-child trees for airport total cargo vs domestic/international cargo, update FTS5 indexing, and regenerate vector embeddings.

---

### 28. What would you change if you knew cargo was coming from the start?
**Answer**:
I would not have created domain-specific columns like `airline` or `commodity` directly on the `series` table. Instead, I would have designed a generic EAV / faceted dimension table (`series_dimensions (series_id, dimension_key, dimension_value)`) and a first-class `metric` column from day one.
