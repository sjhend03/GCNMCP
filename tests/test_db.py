"""
tests/test_db.py — tests for src/db.py

Covers:
  - Connection type and row_factory
  - WAL journal mode and foreign-key enforcement
  - Schema idempotency (safe to open the same DB twice)
  - All expected tables and indexes exist with the right column names
  - Correct PK and UNIQUE constraints on circulars / circular_events
  - FTS5 virtual table supports MATCH queries on subject and body
"""

import sqlite3

import pytest

from src.db import get_connection


# ── helpers ──────────────────────────────────────────────────────────────────

def _open(tmp_path):
    return get_connection(tmp_path / "test.sqlite")


def _insert_circular(conn, circular_id_raw="43493", circular_id_int=43493, record_hash="abc"):
    conn.execute(
        """
        INSERT INTO circulars (
            circular_id_raw, circular_id_int,
            subject, body, created_on, submitter, format,
            raw_event_id, primary_event_raw, primary_event_norm,
            extraction_source, llm_confidence, record_hash
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            circular_id_raw, circular_id_int,
            "GRB 260120B: Swift-BAT refined analysis",
            "Further analysis of BAT GRB 260120B.",
            1769036892952, "Tester", "text/plain",
            "GRB 260120B", "GRB 260120B", "GRB260120B",
            "eventId", None, record_hash,
        ),
    )
    conn.commit()


# ── connection basics ─────────────────────────────────────────────────────────

def test_returns_sqlite_connection(tmp_path):
    conn = _open(tmp_path)
    try:
        assert isinstance(conn, sqlite3.Connection)
    finally:
        conn.close()


def test_uses_row_factory(tmp_path):
    conn = _open(tmp_path)
    try:
        row = conn.execute("SELECT 42 AS answer").fetchone()
        assert isinstance(row, sqlite3.Row)
        assert row["answer"] == 42
    finally:
        conn.close()


def test_journal_mode_is_wal(tmp_path):
    conn = _open(tmp_path)
    try:
        mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert mode == "wal"
    finally:
        conn.close()


def test_foreign_keys_enabled(tmp_path):
    conn = _open(tmp_path)
    try:
        assert conn.execute("PRAGMA foreign_keys;").fetchone()[0] == 1
    finally:
        conn.close()


def test_schema_is_idempotent(tmp_path):
    """Opening the same file twice must not raise."""
    db_path = tmp_path / "test.sqlite"
    c1 = get_connection(db_path)
    c1.close()
    c2 = get_connection(db_path)
    c2.close()


# ── tables exist ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("table", ["circulars", "circular_events", "circulars_fts"])
def test_table_exists(tmp_path, table):
    conn = _open(tmp_path)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        assert row is not None, f"Table '{table}' not found"
    finally:
        conn.close()


# ── indexes exist ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("idx", [
    "idx_circulars_circular_id_int",
    "idx_circulars_primary_event_norm",
    "idx_circular_events_event_norm",
    "idx_circulars_created_on",
])
def test_index_exists(tmp_path, idx):
    conn = _open(tmp_path)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name=?", (idx,)
        ).fetchone()
        assert row is not None, f"Index '{idx}' not found"
    finally:
        conn.close()


# ── column names ──────────────────────────────────────────────────────────────

def test_circulars_has_all_expected_columns(tmp_path):
    conn = _open(tmp_path)
    try:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(circulars)").fetchall()}
        required = {
            "circular_id_raw", "circular_id_int", "subject", "body", "created_on",
            "submitter", "format", "raw_event_id", "primary_event_raw",
            "primary_event_norm", "extraction_source", "llm_confidence", "record_hash",
        }
        assert required <= cols
    finally:
        conn.close()


def test_circular_events_has_all_expected_columns(tmp_path):
    conn = _open(tmp_path)
    try:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(circular_events)").fetchall()}
        assert {"circular_id_raw", "event_norm", "is_primary"} <= cols
    finally:
        conn.close()


# ── circulars table constraints ───────────────────────────────────────────────

def test_can_insert_and_retrieve_circular(tmp_path):
    conn = _open(tmp_path)
    try:
        _insert_circular(conn)
        row = conn.execute(
            "SELECT * FROM circulars WHERE circular_id_raw = ?", ("43493",)
        ).fetchone()
        assert row is not None
        assert row["primary_event_norm"] == "GRB260120B"
        assert row["circular_id_int"] == 43493
    finally:
        conn.close()


def test_circular_id_raw_is_unique(tmp_path):
    conn = _open(tmp_path)
    try:
        _insert_circular(conn)
        with pytest.raises(sqlite3.IntegrityError):
            _insert_circular(conn)
    finally:
        conn.close()


def test_lookup_by_circular_id_int(tmp_path):
    conn = _open(tmp_path)
    try:
        _insert_circular(conn)
        row = conn.execute(
            "SELECT circular_id_raw FROM circulars WHERE circular_id_int = ?", (43493,)
        ).fetchone()
        assert row is not None
        assert row["circular_id_raw"] == "43493"
    finally:
        conn.close()


# ── circular_events table constraints ─────────────────────────────────────────

def test_can_insert_and_retrieve_event(tmp_path):
    conn = _open(tmp_path)
    try:
        _insert_circular(conn)
        conn.execute(
            "INSERT INTO circular_events (circular_id_raw, event_norm, is_primary) VALUES (?,?,?)",
            ("43493", "GRB260120B", 1),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM circular_events WHERE circular_id_raw = ?", ("43493",)
        ).fetchone()
        assert row["event_norm"] == "GRB260120B"
        assert row["is_primary"] == 1
    finally:
        conn.close()


def test_circular_events_unique_constraint(tmp_path):
    conn = _open(tmp_path)
    try:
        _insert_circular(conn)
        conn.execute(
            "INSERT INTO circular_events (circular_id_raw, event_norm, is_primary) VALUES (?,?,?)",
            ("43493", "GRB260120B", 1),
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO circular_events (circular_id_raw, event_norm, is_primary) VALUES (?,?,?)",
                ("43493", "GRB260120B", 0),
            )
            conn.commit()
    finally:
        conn.close()


def test_circular_events_fk_rejects_orphan(tmp_path):
    conn = _open(tmp_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO circular_events (circular_id_raw, event_norm, is_primary) VALUES (?,?,?)",
                ("DOES_NOT_EXIST", "GRB260120B", 1),
            )
            conn.commit()
    finally:
        conn.close()


def test_one_circular_can_have_multiple_events(tmp_path):
    conn = _open(tmp_path)
    try:
        _insert_circular(conn)
        for event, primary in [("GRB260120B", 1), ("EP260119A", 0)]:
            conn.execute(
                "INSERT OR IGNORE INTO circular_events (circular_id_raw, event_norm, is_primary) VALUES (?,?,?)",
                ("43493", event, primary),
            )
        conn.commit()
        rows = conn.execute(
            "SELECT event_norm FROM circular_events WHERE circular_id_raw = ?", ("43493",)
        ).fetchall()
        assert {r["event_norm"] for r in rows} == {"GRB260120B", "EP260119A"}
    finally:
        conn.close()


# ── FTS5 virtual table ────────────────────────────────────────────────────────

def test_fts_match_on_subject(tmp_path):
    conn = _open(tmp_path)
    try:
        conn.execute(
            "INSERT INTO circulars_fts (circular_id_raw, subject, body) VALUES (?,?,?)",
            ("43493", "GRB 260120B Swift-BAT refined analysis", "Further analysis."),
        )
        conn.commit()
        rows = conn.execute(
            "SELECT * FROM circulars_fts WHERE circulars_fts MATCH ?", ("refined",)
        ).fetchall()
        assert len(rows) == 1
    finally:
        conn.close()


def test_fts_match_on_body(tmp_path):
    conn = _open(tmp_path)
    try:
        conn.execute(
            "INSERT INTO circulars_fts (circular_id_raw, subject, body) VALUES (?,?,?)",
            ("43493", "Optical follow-up", "Spectroscopic redshift z = 1.23 was measured."),
        )
        conn.commit()
        rows = conn.execute(
            "SELECT * FROM circulars_fts WHERE circulars_fts MATCH ?", ("redshift",)
        ).fetchall()
        assert len(rows) == 1
    finally:
        conn.close()


def test_fts_no_match_returns_empty(tmp_path):
    conn = _open(tmp_path)
    try:
        conn.execute(
            "INSERT INTO circulars_fts (circular_id_raw, subject, body) VALUES (?,?,?)",
            ("43493", "Some subject", "Some body text."),
        )
        conn.commit()
        rows = conn.execute(
            "SELECT * FROM circulars_fts WHERE circulars_fts MATCH ?", ("xyznonexistent",)
        ).fetchall()
        assert rows == []
    finally:
        conn.close()


def test_fts_multiple_rows_distinct_match(tmp_path):
    conn = _open(tmp_path)
    try:
        conn.execute(
            "INSERT INTO circulars_fts (circular_id_raw, subject, body) VALUES (?,?,?)",
            ("1", "GRB afterglow optical", "Detected optical transient."),
        )
        conn.execute(
            "INSERT INTO circulars_fts (circular_id_raw, subject, body) VALUES (?,?,?)",
            ("2", "Radio observations", "No optical detected at the position."),
        )
        conn.commit()
        rows = conn.execute(
            "SELECT * FROM circulars_fts WHERE circulars_fts MATCH ?", ("optical",)
        ).fetchall()
        assert len(rows) == 2
    finally:
        conn.close()
