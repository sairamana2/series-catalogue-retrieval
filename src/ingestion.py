"""Data ingestion pipeline: CSV validation, cleaning, normalization, hierarchy parsing, and indexing."""

import csv
import json
import logging
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np

from config import (
    AIRLINE_ALIASES,
    AIRPORT_ALIASES,
    CURRENCY_ALIASES,
    DEFAULT_DATA_PATH,
    DEFAULT_DB_PATH,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_VECTOR_IDS_PATH,
    DEFAULT_VECTORS_PATH,
    FLOW_ALIASES,
    FREQUENCY_ALIASES,
)
from src.database import get_db_connection, init_db
from src.normalization import (
    build_search_tokens,
    clean_text,
    extract_record_entities,
)

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "Identifier",
    "Parent",
    "ChildTree1",
    "ChildTree1_Name",
    "ChildTree2",
    "ChildTree2_Name",
    "Title",
    "Category",
    "SubCategory",
    "Subset",
    "Frequency",
    "Unit",
    "Currency",
    "Discontinued",
]


class IngestionValidationError(Exception):
    """Raised when CSV input validation fails."""
    pass


def validate_csv(csv_path: Union[str, Path]) -> List[Dict[str, str]]:
    """Validate CSV headers, identifiers, duplicates, and integrity."""
    path = Path(csv_path)
    if not path.exists():
        raise IngestionValidationError(f"File not found: {path}")

    with open(path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise IngestionValidationError("CSV file is empty or missing headers.")

        missing_cols = set(REQUIRED_COLUMNS) - set(reader.fieldnames)
        if missing_cols:
            raise IngestionValidationError(f"Missing required columns in CSV: {missing_cols}")

        rows = list(reader)

    if not rows:
        raise IngestionValidationError("CSV contains no data rows.")

    # Check unique identifiers
    identifiers: List[str] = []
    seen_ids: Set[str] = set()
    for idx, r in enumerate(rows, start=2):
        ident = r["Identifier"].strip()
        if not ident:
            raise IngestionValidationError(f"Row {idx} has empty Identifier.")
        if ident in seen_ids:
            raise IngestionValidationError(f"Duplicate Identifier found: '{ident}' at row {idx}.")
        seen_ids.add(ident)
        identifiers.append(ident)

    # Validate parent and child hierarchy references
    all_parents = set(r["Parent"].strip() for r in rows if r["Parent"] and r["Parent"].strip())
    missing_parents = all_parents - seen_ids
    if missing_parents:
        raise IngestionValidationError(f"Hierarchy reference error: Parents not found in dataset: {missing_parents}")

    for r in rows:
        for tree_col in ["ChildTree1", "ChildTree2"]:
            raw_tree = r.get(tree_col, "")
            if raw_tree and raw_tree.strip():
                children = [c.strip() for c in raw_tree.split(",") if c.strip()]
                missing_children = set(children) - seen_ids
                if missing_children:
                    raise IngestionValidationError(
                        f"Record {r['Identifier']} has broken child references in {tree_col}: {missing_children}"
                    )

    logger.info(f"Validated {len(rows)} records successfully. Zero broken hierarchy links.")
    return rows


def build_and_save_embeddings(
    records: List[Dict[str, Any]],
    vectors_path: Path = DEFAULT_VECTORS_PATH,
    vector_ids_path: Path = DEFAULT_VECTOR_IDS_PATH,
) -> None:
    """Generate dense embeddings for each record and save to disk."""
    try:
        from fastembed import TextEmbedding

        logger.info(f"Loading embedding model: {DEFAULT_EMBEDDING_MODEL}...")
        model = TextEmbedding(model_name=DEFAULT_EMBEDDING_MODEL)

        # Build embedding texts: combination of clean title and core categorical metadata
        texts_to_embed = [
            f"{r['clean_title']} | {r['category']} - {r['subcategory']} | Frequency: {r['frequency']} | Unit: {r['unit']} | Currency: {r['currency']}"
            for r in records
        ]

        logger.info(f"Generating dense embeddings for {len(texts_to_embed)} records...")
        embeddings = list(model.embed(texts_to_embed))
        vec_array = np.array(embeddings, dtype=np.float32)

        # Normalize embeddings to unit length for cosine similarity via dot product
        norms = np.linalg.norm(vec_array, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        vec_array = vec_array / norms

        np.save(vectors_path, vec_array)
        vector_ids = [r["identifier"] for r in records]
        with open(vector_ids_path, mode="w", encoding="utf-8") as f:
            json.dump(vector_ids, f)

        logger.info(f"Saved {vec_array.shape[0]} embeddings of dimension {vec_array.shape[1]} to {vectors_path}.")
    except Exception as e:
        logger.warning(f"Dense embedding generation skipped or failed: {e}. Lexical retrieval will remain active.")


def ingest_catalogue(
    csv_path: Union[str, Path] = DEFAULT_DATA_PATH,
    db_path: Union[str, Path] = DEFAULT_DB_PATH,
    build_vectors: bool = True,
    vectors_path: Path = DEFAULT_VECTORS_PATH,
    vector_ids_path: Path = DEFAULT_VECTOR_IDS_PATH,
) -> Dict[str, Any]:
    """Execute complete ingestion pipeline: validate, clean, store, index, and embed."""
    logger.info(f"Starting ingestion from {csv_path} to {db_path}...")
    rows = validate_csv(csv_path)

    # Initialize fresh database
    conn = init_db(db_path, drop_existing=True)

    cleaned_records: List[Dict[str, Any]] = []
    hierarchy_edges: List[Tuple[str, str, int, str, int]] = []

    for r in rows:
        ident = r["Identifier"].strip()
        raw_title = r["Title"]
        clean_title = clean_text(raw_title)
        category = r["Category"].strip()
        subcategory = r["SubCategory"].strip()
        subset = r["Subset"].strip()
        frequency = r["Frequency"].strip()
        unit = r["Unit"].strip()
        currency = r["Currency"].strip()
        discontinued = r["Discontinued"].strip().upper()
        parent = r["Parent"].strip() if r["Parent"] and r["Parent"].strip() else None

        entities = extract_record_entities(r)
        search_text = build_search_tokens(
            identifier=ident,
            clean_title=clean_title,
            category=category,
            subcategory=subcategory,
            subset=subset,
            frequency=frequency,
            unit=unit,
            currency=currency,
            entities=entities,
        )

        record_dict = {
            "identifier": ident,
            "title": raw_title,
            "clean_title": clean_title,
            "category": category,
            "subcategory": subcategory,
            "subset": subset,
            "frequency": frequency,
            "unit": unit,
            "currency": currency,
            "discontinued": discontinued,
            "parent": parent,
            "airline": entities["airline"],
            "airport": entities["airport"],
            "commodity": entities["commodity"],
            "flow": entities["flow"],
            "calc_type": entities["calc_type"],
            "search_text": search_text,
            "raw_json": json.dumps(r, ensure_ascii=False),
        }
        cleaned_records.append(record_dict)

        # Parse ChildTree1
        ct1 = r.get("ChildTree1", "").strip()
        ct1_name = clean_text(r.get("ChildTree1_Name", "")) or "Default"
        if ct1:
            for order, child in enumerate(ct1.split(","), start=1):
                c_id = child.strip()
                if c_id:
                    hierarchy_edges.append((ident, c_id, 1, ct1_name, order))

        # Parse ChildTree2
        ct2 = r.get("ChildTree2", "").strip()
        ct2_name = clean_text(r.get("ChildTree2_Name", "")) or "Calculated Indicators"
        if ct2:
            for order, child in enumerate(ct2.split(","), start=1):
                c_id = child.strip()
                if c_id:
                    hierarchy_edges.append((ident, c_id, 2, ct2_name, order))

    with conn:
        # 1. Insert into series table
        conn.executemany("""
        INSERT INTO series (
            identifier, title, clean_title, category, subcategory, subset,
            frequency, unit, currency, discontinued, parent,
            airline, airport, commodity, flow, calc_type, search_text, raw_json
        ) VALUES (
            :identifier, :title, :clean_title, :category, :subcategory, :subset,
            :frequency, :unit, :currency, :discontinued, :parent,
            :airline, :airport, :commodity, :flow, :calc_type, :search_text, :raw_json
        );
        """, cleaned_records)

        # 2. Insert into series_hierarchy table
        conn.executemany("""
        INSERT INTO series_hierarchy (parent_id, child_id, tree_number, tree_name, child_order)
        VALUES (?, ?, ?, ?, ?);
        """, hierarchy_edges)

        # 3. Populate series_aliases table
        alias_rows = []
        for alias, can in AIRPORT_ALIASES.items():
            alias_rows.append((alias, can, "airport"))
        for alias, can in AIRLINE_ALIASES.items():
            alias_rows.append((alias, can, "airline"))
        for alias, d in CURRENCY_ALIASES.items():
            alias_rows.append((alias, d["currency"], "currency"))
        for alias, can in FREQUENCY_ALIASES.items():
            alias_rows.append((alias, can, "frequency"))
        for alias, can in FLOW_ALIASES.items():
            alias_rows.append((alias, can, "flow"))

        conn.executemany("""
        INSERT OR REPLACE INTO series_aliases (alias, canonical_value, entity_type)
        VALUES (?, ?, ?);
        """, alias_rows)

        # 4. Populate FTS5 index
        conn.execute("""
        INSERT INTO series_fts(rowid, identifier, clean_title, category, subcategory, subset, frequency, unit, currency, airline, airport, commodity, search_text)
        SELECT rowid, identifier, clean_title, category, subcategory, subset, frequency, unit, currency, airline, airport, commodity, search_text
        FROM series;
        """)

    conn.close()
    logger.info(f"Loaded {len(cleaned_records)} series and {len(hierarchy_edges)} hierarchy edges into {db_path}.")

    if build_vectors:
        build_and_save_embeddings(cleaned_records, vectors_path, vector_ids_path)

    return {
        "status": "success",
        "total_records": len(cleaned_records),
        "total_hierarchy_edges": len(hierarchy_edges),
        "db_path": str(db_path),
    }
