"""
tests/test_indexer.py — tests for src/indexer.py

Covers:
  - sha1_text: determinism, sensitivity to input, output format
  - parse_circular_id: int, whole-float, fractional float, numeric string,
      non-numeric string, None, empty string
  - upsert_circular: full insert into all three tables, field mapping,
      idempotency on unchanged records, update on changed records,
      FTS sync on update, event extraction fallbacks (subject/body/none),
      multi-event records, null-byte sanitisation, missing circularId error
  - iter_json_records: single object, list, JSONL, blank JSONL lines,
      directory of .json, directory with .jsonl, unsupported extension,
      missing path
  - ingest_path: return count, DB population, idempotency, directory ingestion
"""

import json

import pytest

from src.db import get_connection
from src.indexer import (
    ingest_path,
    iter_json_records,
    parse_circular_id,
    sha1_text,
    upsert_circular,
)


# ── test helpers ──────────────────────────────────────────────────────────────

def make_record(
    circular_id=43493,
    subject="GRB 260120B: Swift-BAT refined analysis",
    body="Using the data set from T-769 to T+303 sec, we report further analysis of BAT GRB 260120B.",
    event_id="GRB 260120B",
    created_on=1769036892952,
    submitter="Test Submitter <test@example.com>",
):
    return {
        "circularId": circular_id,
        "subject": subject,
        "eventId": event_id,
        "createdOn": created_on,
        "submitter": submitter,
        "format": "text/plain",
        "body": body,
    }


def fresh_db(tmp_path):
    return get_connection(tmp_path / "test.sqlite")


# ── sha1_text ─────────────────────────────────────────────────────────────────

def test_sha1_is_deterministic():
    assert sha1_text("hello") == sha1_text("hello")


def test_sha1_sensitive_to_input():
    assert sha1_text("abc") != sha1_text("abcd")


def test_sha1_returns_40_char_hex():
    h = sha1_text("anything")
    assert len(h) == 40
    assert all(c in "0123456789abcdef" for c in h)


def test_sha1_handles_empty_string():
    h = sha1_text("")
    assert len(h) == 40


# ── parse_circular_id ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("value, expected_raw, expected_int", [
    (43493,       "43493", 43493),
    (43493.0,     "43493", 43493),
    ("43493",     "43493", 43493),
    ("43493.0",   "43493", 43493),
    (None,        None,    None),
    ("",          None,    None),
])
def test_parse_circular_id_standard_cases(value, expected_raw, expected_int):
    raw, integer = parse_circular_id(value)
    assert raw == expected_raw
    assert integer == expected_int


def test_parse_circular_id_fractional_float():
    raw, integer = parse_circular_id(43493.5)
    assert raw is not None       # has a string form
    assert integer is None       # not an integer


def test_parse_circular_id_non_numeric_string():
    raw, integer = parse_circular_id("CIRCULAR-XYZ")
    assert raw == "CIRCULAR-XYZ"
    assert integer is None


# ── upsert_circular — basic insert ────────────────────────────────────────────

def test_upsert_inserts_into_circulars(tmp_path):
    conn = fresh_db(tmp_path)
    upsert_circular(conn, make_record())
    conn.commit()
    row = conn.execute(
        "SELECT * FROM circulars WHERE circular_id_raw = ?", ("43493",)
    ).fetchone()
    assert row is not None
    assert row["subject"] == "GRB 260120B: Swift-BAT refined analysis"
    assert row["primary_event_norm"] == "GRB260120B"
    assert row["circular_id_int"] == 43493
    assert row["extraction_source"] == "eventId"
    conn.close()


def test_upsert_populates_circular_events(tmp_path):
    conn = fresh_db(tmp_path)
    upsert_circular(conn, make_record())
    conn.commit()
    rows = conn.execute(
        "SELECT * FROM circular_events WHERE circular_id_raw = ?", ("43493",)
    ).fetchall()
    assert len(rows) >= 1
    primary_rows = [r for r in rows if r["is_primary"] == 1]
    assert len(primary_rows) == 1
    assert primary_rows[0]["event_norm"] == "GRB260120B"
    conn.close()


def test_upsert_populates_fts(tmp_path):
    conn = fresh_db(tmp_path)
    upsert_circular(conn, make_record())
    conn.commit()
    rows = conn.execute(
        "SELECT * FROM circulars_fts WHERE circulars_fts MATCH ?", ("refined",)
    ).fetchall()
    assert len(rows) == 1
    conn.close()


def test_upsert_maps_created_on_field(tmp_path):
    conn = fresh_db(tmp_path)
    upsert_circular(conn, make_record(created_on=1769036892952))
    conn.commit()
    row = conn.execute(
        "SELECT created_on FROM circulars WHERE circular_id_raw = ?", ("43493",)
    ).fetchone()
    assert row["created_on"] == 1769036892952
    conn.close()


def test_upsert_maps_submitter_field(tmp_path):
    conn = fresh_db(tmp_path)
    upsert_circular(conn, make_record(submitter="Jane Smith <jane@example.com>"))
    conn.commit()
    row = conn.execute(
        "SELECT submitter FROM circulars WHERE circular_id_raw = ?", ("43493",)
    ).fetchone()
    assert "Jane Smith" in row["submitter"]
    conn.close()


# ── upsert_circular — idempotency ─────────────────────────────────────────────

def test_upsert_skips_unchanged_record(tmp_path):
    conn = fresh_db(tmp_path)
    record = make_record()
    upsert_circular(conn, record)
    conn.commit()
    upsert_circular(conn, record)
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM circulars").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM circulars_fts").fetchone()[0] == 1
    conn.close()


def test_upsert_updates_subject_when_record_changes(tmp_path):
    conn = fresh_db(tmp_path)
    record = make_record()
    upsert_circular(conn, record)
    conn.commit()
    updated = dict(record, subject="GRB 260120B: Updated subject")
    upsert_circular(conn, updated)
    conn.commit()
    row = conn.execute(
        "SELECT subject FROM circulars WHERE circular_id_raw = ?", ("43493",)
    ).fetchone()
    assert row["subject"] == "GRB 260120B: Updated subject"
    conn.close()


def test_upsert_syncs_fts_when_body_changes(tmp_path):
    conn = fresh_db(tmp_path)
    record = make_record()
    upsert_circular(conn, record)
    conn.commit()
    updated = dict(record, body="Completely new body discussing neutrino afterglow flux.")
    upsert_circular(conn, updated)
    conn.commit()
    rows = conn.execute(
        "SELECT * FROM circulars_fts WHERE circulars_fts MATCH ?", ("neutrino",)
    ).fetchall()
    assert len(rows) == 1
    # Old body term should no longer match
    old_rows = conn.execute(
        "SELECT * FROM circulars_fts WHERE circulars_fts MATCH ?", ("\"T-769\"",)
    ).fetchall()
    assert len(old_rows) == 0
    conn.close()


# ── upsert_circular — event extraction fallbacks ──────────────────────────────

def test_upsert_extracts_event_from_subject_when_event_id_missing(tmp_path):
    conn = fresh_db(tmp_path)
    record = make_record(event_id=None, subject="EP260119a: optical counterpart candidate")
    upsert_circular(conn, record)
    conn.commit()
    row = conn.execute(
        "SELECT primary_event_norm, extraction_source FROM circulars WHERE circular_id_raw = ?",
        ("43493",),
    ).fetchone()
    assert row["primary_event_norm"] == "EP260119A"
    assert row["extraction_source"] == "subject"
    conn.close()


def test_upsert_extracts_event_from_body_as_last_resort(tmp_path):
    conn = fresh_db(tmp_path)
    record = make_record(
        event_id=None,
        subject="Optical follow-up observations",
        body="We observed the field of GRB 260120B and found a fading optical source.",
    )
    upsert_circular(conn, record)
    conn.commit()
    row = conn.execute(
        "SELECT primary_event_norm, extraction_source FROM circulars WHERE circular_id_raw = ?",
        ("43493",),
    ).fetchone()
    assert row["primary_event_norm"] == "GRB260120B"
    assert row["extraction_source"] == "body"
    conn.close()


def test_upsert_stores_null_event_norm_when_no_event_found(tmp_path):
    conn = fresh_db(tmp_path)
    record = make_record(
        event_id=None,
        subject="General report on observatory status",
        body="Nothing notable detected in the field.",
    )
    upsert_circular(conn, record)
    conn.commit()
    row = conn.execute(
        "SELECT primary_event_norm, extraction_source FROM circulars WHERE circular_id_raw = ?",
        ("43493",),
    ).fetchone()
    assert row["primary_event_norm"] is None
    assert row["extraction_source"] == "none"
    conn.close()


def test_upsert_stores_multiple_events_from_body(tmp_path):
    conn = fresh_db(tmp_path)
    record = make_record(
        event_id=None,
        subject="Multi-event follow-up",
        body="We observed GRB 260120B and compared it with EP260119a at the same field.",
    )
    upsert_circular(conn, record)
    conn.commit()
    rows = conn.execute(
        "SELECT event_norm FROM circular_events WHERE circular_id_raw = ?", ("43493",)
    ).fetchall()
    event_norms = {r["event_norm"] for r in rows}
    assert "GRB260120B" in event_norms
    assert "EP260119A" in event_norms
    conn.close()


def test_upsert_sanitises_null_bytes_in_subject(tmp_path):
    conn = fresh_db(tmp_path)
    record = make_record(subject="GRB\x00260120B: analysis\x00")
    upsert_circular(conn, record)
    conn.commit()
    row = conn.execute(
        "SELECT subject FROM circulars WHERE circular_id_raw = ?", ("43493",)
    ).fetchone()
    assert "\x00" not in row["subject"]
    conn.close()


def test_upsert_raises_on_missing_circular_id(tmp_path):
    conn = fresh_db(tmp_path)
    record = make_record()
    del record["circularId"]
    with pytest.raises(ValueError, match="circularId"):
        upsert_circular(conn, record)
    conn.close()


# ── iter_json_records ─────────────────────────────────────────────────────────

def test_iter_single_json_object(tmp_path):
    path = tmp_path / "one.json"
    path.write_text(json.dumps(make_record()), encoding="utf-8")
    records = list(iter_json_records(path))
    assert len(records) == 1
    assert records[0]["circularId"] == 43493


def test_iter_json_array(tmp_path):
    path = tmp_path / "many.json"
    recs = [make_record(1), make_record(2), make_record(3)]
    path.write_text(json.dumps(recs), encoding="utf-8")
    records = list(iter_json_records(path))
    assert len(records) == 3
    assert {r["circularId"] for r in records} == {1, 2, 3}


def test_iter_jsonl_file(tmp_path):
    path = tmp_path / "data.jsonl"
    lines = "\n".join(json.dumps(make_record(i)) for i in [10, 20, 30])
    path.write_text(lines, encoding="utf-8")
    records = list(iter_json_records(path))
    assert {r["circularId"] for r in records} == {10, 20, 30}


def test_iter_jsonl_skips_blank_lines(tmp_path):
    path = tmp_path / "gaps.jsonl"
    path.write_text(
        json.dumps(make_record(1)) + "\n\n" + json.dumps(make_record(2)) + "\n",
        encoding="utf-8",
    )
    records = list(iter_json_records(path))
    assert len(records) == 2


def test_iter_directory_of_json_files(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    for i, cid in enumerate([100, 200, 300]):
        (data / f"{i:04d}.json").write_text(json.dumps(make_record(cid)), encoding="utf-8")
    records = list(iter_json_records(data))
    assert {r["circularId"] for r in records} == {100, 200, 300}


def test_iter_directory_with_mixed_json_and_jsonl(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "a.json").write_text(json.dumps(make_record(1)), encoding="utf-8")
    (data / "b.jsonl").write_text(
        json.dumps(make_record(2)) + "\n" + json.dumps(make_record(3)),
        encoding="utf-8",
    )
    records = list(iter_json_records(data))
    assert {r["circularId"] for r in records} == {1, 2, 3}


def test_iter_raises_for_unsupported_extension(tmp_path):
    path = tmp_path / "data.csv"
    path.write_text("col1,col2\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        list(iter_json_records(path))


def test_iter_raises_for_missing_path(tmp_path):
    with pytest.raises(FileNotFoundError):
        list(iter_json_records(tmp_path / "nonexistent_dir"))


# ── ingest_path ───────────────────────────────────────────────────────────────

def test_ingest_returns_correct_count(tmp_path):
    db_path = tmp_path / "test.sqlite"
    json_path = tmp_path / "data.json"
    json_path.write_text(json.dumps([make_record(i) for i in range(5)]), encoding="utf-8")
    assert ingest_path(db_path, json_path) == 5


def test_ingest_populates_database(tmp_path):
    db_path = tmp_path / "test.sqlite"
    json_path = tmp_path / "data.json"
    json_path.write_text(json.dumps(make_record()), encoding="utf-8")
    ingest_path(db_path, json_path)
    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT primary_event_norm FROM circulars WHERE circular_id_raw = ?", ("43493",)
    ).fetchone()
    conn.close()
    assert row is not None
    assert row["primary_event_norm"] == "GRB260120B"


def test_ingest_is_idempotent(tmp_path):
    db_path = tmp_path / "test.sqlite"
    json_path = tmp_path / "data.json"
    json_path.write_text(json.dumps(make_record()), encoding="utf-8")
    ingest_path(db_path, json_path)
    ingest_path(db_path, json_path)
    conn = get_connection(db_path)
    assert conn.execute("SELECT COUNT(*) FROM circulars").fetchone()[0] == 1
    conn.close()


def test_ingest_from_directory(tmp_path):
    db_path = tmp_path / "test.sqlite"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for cid in [1, 2, 3]:
        (data_dir / f"{cid}.json").write_text(json.dumps(make_record(cid)), encoding="utf-8")
    count = ingest_path(db_path, data_dir)
    assert count == 3
    conn = get_connection(db_path)
    assert conn.execute("SELECT COUNT(*) FROM circulars").fetchone()[0] == 3
    conn.close()


def test_ingest_creates_db_if_not_exists(tmp_path):
    db_path = tmp_path / "brand_new.sqlite"
    json_path = tmp_path / "data.json"
    json_path.write_text(json.dumps(make_record()), encoding="utf-8")
    assert not db_path.exists()
    ingest_path(db_path, json_path)
    assert db_path.exists()
