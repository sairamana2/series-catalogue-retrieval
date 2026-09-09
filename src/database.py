"""Database layer for Time Series Catalogue using SQLite and FTS5."""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from config import DEFAULT_DB_PATH


def get_db_connection(db_path: Union[str, Path] = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Create and configure a SQLite connection."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Union[str, Path] = DEFAULT_DB_PATH, drop_existing: bool = False) -> sqlite3.Connection:
    """Initialize SQLite database tables, indexes, and FTS5 virtual table."""
    conn = get_db_connection(db_path)
    with conn:
        if drop_existing:
            conn.execute("DROP TABLE IF EXISTS series_fts;")
            conn.execute("DROP TABLE IF EXISTS series_hierarchy;")
            conn.execute("DROP TABLE IF EXISTS series_aliases;")
            conn.execute("DROP TABLE IF EXISTS series;")

        # Primary source-of-truth table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS series (
            rowid INTEGER PRIMARY KEY AUTOINCREMENT,
            identifier TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            clean_title TEXT NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT NOT NULL,
            subset TEXT NOT NULL,
            frequency TEXT NOT NULL,
            unit TEXT NOT NULL,
            currency TEXT NOT NULL,
            discontinued TEXT NOT NULL,
            parent TEXT,
            airline TEXT,
            airport TEXT,
            commodity TEXT,
            flow TEXT,
            calc_type TEXT,
            search_text TEXT NOT NULL,
            raw_json TEXT NOT NULL
        );
        """)

        # Indexes on structured fields for fast filtering
        conn.execute("CREATE INDEX IF NOT EXISTS idx_series_identifier ON series(identifier);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_series_category ON series(category);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_series_frequency ON series(frequency);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_series_discontinued ON series(discontinued);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_series_airline ON series(airline);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_series_airport ON series(airport);")

        # Structured Hierarchy Table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS series_hierarchy (
            parent_id TEXT NOT NULL,
            child_id TEXT NOT NULL,
            tree_number INTEGER NOT NULL,
            tree_name TEXT NOT NULL,
            child_order INTEGER NOT NULL,
            PRIMARY KEY (parent_id, child_id, tree_number),
            FOREIGN KEY (parent_id) REFERENCES series(identifier) ON DELETE CASCADE,
            FOREIGN KEY (child_id) REFERENCES series(identifier) ON DELETE CASCADE
        );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_hierarchy_parent ON series_hierarchy(parent_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_hierarchy_child ON series_hierarchy(child_id);")

        # Dynamic Alias Table
        conn.execute("""
        CREATE TABLE IF NOT EXISTS series_aliases (
            alias TEXT PRIMARY KEY,
            canonical_value TEXT NOT NULL,
            entity_type TEXT NOT NULL
        );
        """)

        # FTS5 Virtual Table for BM25 Lexical Retrieval
        conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS series_fts USING fts5(
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
        """)

    return conn


def get_series_by_id(identifier: str, conn: Optional[sqlite3.Connection] = None, db_path: Union[str, Path] = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    """Fetch a single series record by identifier."""
    should_close = False
    if conn is None:
        conn = get_db_connection(db_path)
        should_close = True
    try:
        cur = conn.execute("SELECT * FROM series WHERE identifier = ?", (identifier,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        if should_close:
            conn.close()


def get_children(identifier: str, tree_number: Optional[int] = None, conn: Optional[sqlite3.Connection] = None, db_path: Union[str, Path] = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Fetch all child series for a given parent identifier."""
    should_close = False
    if conn is None:
        conn = get_db_connection(db_path)
        should_close = True
    try:
        query = """
        SELECT s.*, h.tree_number, h.tree_name, h.child_order
        FROM series_hierarchy h
        JOIN series s ON s.identifier = h.child_id
        WHERE h.parent_id = ?
        """
        params: List[Any] = [identifier]
        if tree_number is not None:
            query += " AND h.tree_number = ?"
            params.append(tree_number)
        query += " ORDER BY h.tree_number, h.child_order ASC"

        cur = conn.execute(query, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        if should_close:
            conn.close()


def get_all_series(conn: Optional[sqlite3.Connection] = None, db_path: Union[str, Path] = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Fetch all series records from the database."""
    should_close = False
    if conn is None:
        conn = get_db_connection(db_path)
        should_close = True
    try:
        cur = conn.execute("SELECT * FROM series ORDER BY rowid ASC")
        return [dict(r) for r in cur.fetchall()]
    finally:
        if should_close:
            conn.close()
