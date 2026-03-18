import sqlite3

from src.db import get_connection


def test_get_connection_returns_sqlite_connection(tmp_path):
    db_path = tmp_path / "test.sqlite"

    conn = get_connection(db_path)

    try:
        assert isinstance(conn, sqlite3.Connection)
    finally:
        conn.close()


def test_get_connection_uses_row_factory(tmp_path):
    db_path = tmp_path / "test.sqlite"

    conn = get_connection(db_path)

    try:
        row = conn.execute("SELECT 1 AS value").fetchone()
        assert isinstance(row, sqlite3.Row)
        assert row["value"] == 1
    finally:
        conn.close()


def test_schema_creates_main_tables(tmp_path):
    db_path = tmp_path / "test.sqlite"

    conn = get_connection(db_path)

    try:
        rows = conn.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type='table'
        """).fetchall()

        table_names = {row["name"] for row in rows}

        assert "circulars" in table_names
        assert "circular_events" in table_names
        assert "circulars_fts" in table_names
    finally:
        conn.close()


def test_schema_creates_expected_indexes(tmp_path):
    db_path = tmp_path / "test.sqlite"

    conn = get_connection(db_path)

    try:
        rows = conn.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type='index'
        """).fetchall()

        index_names = {row["name"] for row in rows}

        assert "idx_circulars_primary_event_norm" in index_names
        assert "idx_circular_events_event_norm" in index_names
        assert "idx_circulars_created_on" in index_names
    finally:
        conn.close()


def test_connection_can_insert_into_circulars(tmp_path):
    db_path = tmp_path / "test.sqlite"

    conn = get_connection(db_path)

    try:
        conn.execute("""
            INSERT INTO circulars (
                circular_id,
                subject,
                body,
                created_on,
                submitter,
                format,
                raw_event_id,
                primary_event_raw,
                primary_event_norm,
                extraction_source,
                llm_confidence,
                record_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            12345,
            "GRB 260120B: Test circular",
            "This is a test body.",
            1769036892952,
            "Test Submitter",
            "text/plain",
            "GRB 260120B",
            "GRB 260120B",
            "GRB260120B",
            "eventId",
            None,
            "abc123hash",
        ))
        conn.commit()

        row = conn.execute("""
            SELECT *
            FROM circulars
            WHERE circular_id = ?
        """, (12345,)).fetchone()

        assert row is not None
        assert row["subject"] == "GRB 260120B: Test circular"
        assert row["primary_event_norm"] == "GRB260120B"
    finally:
        conn.close()


def test_connection_can_insert_into_circular_events(tmp_path):
    db_path = tmp_path / "test.sqlite"

    conn = get_connection(db_path)

    try:
        conn.execute("""
            INSERT INTO circulars (
                circular_id,
                subject,
                body,
                created_on,
                submitter,
                format,
                raw_event_id,
                primary_event_raw,
                primary_event_norm,
                extraction_source,
                llm_confidence,
                record_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            12345,
            "GRB 260120B: Test circular",
            "This is a test body.",
            1769036892952,
            "Test Submitter",
            "text/plain",
            "GRB 260120B",
            "GRB 260120B",
            "GRB260120B",
            "eventId",
            None,
            "abc123hash",
        ))

        conn.execute("""
            INSERT INTO circular_events (
                circular_id,
                event_norm,
                is_primary
            )
            VALUES (?, ?, ?)
        """, (
            12345,
            "GRB260120B",
            1,
        ))
        conn.commit()

        row = conn.execute("""
            SELECT *
            FROM circular_events
            WHERE circular_id = ?
        """, (12345,)).fetchone()

        assert row is not None
        assert row["event_norm"] == "GRB260120B"
        assert row["is_primary"] == 1
    finally:
        conn.close()


def test_connection_can_insert_into_fts_table(tmp_path):
    db_path = tmp_path / "test.sqlite"

    conn = get_connection(db_path)

    try:
        conn.execute("""
            INSERT INTO circulars_fts (rowid, subject, body)
            VALUES (?, ?, ?)
        """, (
            12345,
            "EP260119a: optical counterpart candidate",
            "The source is a good candidate for being the optical counterpart."
        ))
        conn.commit()

        rows = conn.execute("""
            SELECT rowid, subject, body
            FROM circulars_fts
            WHERE circulars_fts MATCH ?
        """, ("optical counterpart",)).fetchall()

        assert len(rows) == 1
        assert rows[0]["rowid"] == 12345
        assert "optical counterpart" in rows[0]["body"]
    finally:
        conn.close()