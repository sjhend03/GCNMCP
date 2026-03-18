import json

from src.db import get_connection
from src.indexer import sha1_text, upsert_circular, iter_json_records, ingest_path


def make_sample_record():
    return {
        "subject": "GRB 260120B: Swift-BAT refined analysis",
        "eventId": "GRB 260120B",
        "submittedHow": "web",
        "createdOn": 1769036892952,
        "circularId": 43493,
        "submitter": "D. R. Sadaula at NASA GSFC <dev.r.sadaula@nasa.gov>",
        "format": "text/plain",
        "body": "Using the data set from T-769 to T+303 sec, we report further analysis of BAT GRB 260120B.",
    }


def test_sha1_text_is_deterministic():
    text = "example circular text"
    assert sha1_text(text) == sha1_text(text)


def test_sha1_text_changes_when_input_changes():
    assert sha1_text("abc") != sha1_text("abcd")


def test_upsert_circular_inserts_into_circulars(tmp_path):
    db_path = tmp_path / "test.sqlite"
    conn = get_connection(db_path)

    try:
        record = make_sample_record()
        upsert_circular(conn, record)
        conn.commit()

        row = conn.execute(
            "SELECT * FROM circulars WHERE circular_id = ?",
            (43493,),
        ).fetchone()

        assert row is not None
        assert row["subject"] == "GRB 260120B: Swift-BAT refined analysis"
        assert row["primary_event_norm"] == "GRB260120B"
        assert row["extraction_source"] == "eventId"
    finally:
        conn.close()


def test_upsert_circular_inserts_into_circular_events(tmp_path):
    db_path = tmp_path / "test.sqlite"
    conn = get_connection(db_path)

    try:
        record = make_sample_record()
        upsert_circular(conn, record)
        conn.commit()

        rows = conn.execute(
            "SELECT * FROM circular_events WHERE circular_id = ?",
            (43493,),
        ).fetchall()

        assert len(rows) == 1
        assert rows[0]["event_norm"] == "GRB260120B"
        assert rows[0]["is_primary"] == 1
    finally:
        conn.close()


def test_upsert_circular_inserts_into_fts(tmp_path):
    db_path = tmp_path / "test.sqlite"
    conn = get_connection(db_path)

    try:
        record = make_sample_record()
        upsert_circular(conn, record)
        conn.commit()

        rows = conn.execute(
            """
            SELECT rowid, subject, body
            FROM circulars_fts
            WHERE circulars_fts MATCH ?
            """,
            ('"Swift-BAT"',),
        ).fetchall()

        assert len(rows) == 1
        assert rows[0]["rowid"] == 43493
        assert "GRB 260120B" in rows[0]["subject"]
    finally:
        conn.close()


def test_upsert_circular_skips_unchanged_record(tmp_path):
    db_path = tmp_path / "test.sqlite"
    conn = get_connection(db_path)

    try:
        record = make_sample_record()

        upsert_circular(conn, record)
        conn.commit()

        upsert_circular(conn, record)
        conn.commit()

        count_circulars = conn.execute(
            "SELECT COUNT(*) AS n FROM circulars"
        ).fetchone()["n"]

        count_events = conn.execute(
            "SELECT COUNT(*) AS n FROM circular_events"
        ).fetchone()["n"]

        count_fts = conn.execute(
            "SELECT COUNT(*) AS n FROM circulars_fts"
        ).fetchone()["n"]

        assert count_circulars == 1
        assert count_events == 1
        assert count_fts == 1
    finally:
        conn.close()


def test_upsert_circular_updates_changed_record(tmp_path):
    db_path = tmp_path / "test.sqlite"
    conn = get_connection(db_path)

    try:
        record = make_sample_record()
        upsert_circular(conn, record)
        conn.commit()

        updated = dict(record)
        updated["subject"] = "GRB 260120B: Updated subject line"
        upsert_circular(conn, updated)
        conn.commit()

        row = conn.execute(
            "SELECT * FROM circulars WHERE circular_id = ?",
            (43493,),
        ).fetchone()

        assert row["subject"] == "GRB 260120B: Updated subject line"
    finally:
        conn.close()


def test_upsert_circular_extracts_event_from_subject_when_event_id_missing(tmp_path):
    db_path = tmp_path / "test.sqlite"
    conn = get_connection(db_path)

    try:
        record = {
            "subject": "EP260119a: COLIBRÍ optical counterpart candidate",
            "eventId": None,
            "createdOn": 1768822574334,
            "circularId": 43450,
            "submitter": "Test Submitter",
            "format": "text/plain",
            "body": "The source is a good candidate for being the optical counterpart.",
        }

        upsert_circular(conn, record)
        conn.commit()

        row = conn.execute(
            "SELECT * FROM circulars WHERE circular_id = ?",
            (43450,),
        ).fetchone()

        assert row["primary_event_norm"] == "EP260119A"
        assert row["extraction_source"] == "subject"
    finally:
        conn.close()


def test_upsert_circular_extracts_event_from_body_when_missing_elsewhere(tmp_path):
    db_path = tmp_path / "test.sqlite"
    conn = get_connection(db_path)

    try:
        record = {
            "subject": "Optical observations",
            "eventId": None,
            "createdOn": 1768822574334,
            "circularId": 50000,
            "submitter": "Test Submitter",
            "format": "text/plain",
            "body": "We observed the field of GRB 260120B and measured a fading source.",
        }

        upsert_circular(conn, record)
        conn.commit()

        row = conn.execute(
            "SELECT * FROM circulars WHERE circular_id = ?",
            (50000,),
        ).fetchone()

        assert row["primary_event_norm"] == "GRB260120B"
        assert row["extraction_source"] == "body"
    finally:
        conn.close()


def test_iter_json_records_reads_single_json_object(tmp_path):
    file_path = tmp_path / "one.json"
    record = make_sample_record()
    file_path.write_text(json.dumps(record), encoding="utf-8")

    records = list(iter_json_records(file_path))

    assert len(records) == 1
    assert records[0]["circularId"] == 43493


def test_iter_json_records_reads_json_list(tmp_path):
    file_path = tmp_path / "many.json"
    records_in = [make_sample_record(), {**make_sample_record(), "circularId": 43494}]
    file_path.write_text(json.dumps(records_in), encoding="utf-8")

    records = list(iter_json_records(file_path))

    assert len(records) == 2
    assert records[0]["circularId"] == 43493
    assert records[1]["circularId"] == 43494


def test_iter_json_records_reads_jsonl(tmp_path):
    file_path = tmp_path / "many.jsonl"
    record1 = make_sample_record()
    record2 = {**make_sample_record(), "circularId": 43494}

    file_path.write_text(
        json.dumps(record1) + "\n" + json.dumps(record2) + "\n",
        encoding="utf-8",
    )

    records = list(iter_json_records(file_path))

    assert len(records) == 2
    assert records[0]["circularId"] == 43493
    assert records[1]["circularId"] == 43494


def test_ingest_path_loads_json_file_into_database(tmp_path):
    db_path = tmp_path / "test.sqlite"
    json_path = tmp_path / "one.json"

    record = make_sample_record()
    json_path.write_text(json.dumps(record), encoding="utf-8")

    count = ingest_path(db_path, json_path)
    assert count == 1

    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM circulars WHERE circular_id = ?",
            (43493,),
        ).fetchone()

        assert row is not None
        assert row["primary_event_norm"] == "GRB260120B"
    finally:
        conn.close()


def test_ingest_path_loads_directory_of_json_files(tmp_path):
    db_path = tmp_path / "test.sqlite"
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    record1 = make_sample_record()
    record2 = {**make_sample_record(), "circularId": 43494, "subject": "GRB 260120C: Test"}

    (data_dir / "a.json").write_text(json.dumps(record1), encoding="utf-8")
    (data_dir / "b.json").write_text(json.dumps(record2), encoding="utf-8")

    count = ingest_path(db_path, data_dir)
    assert count == 2

    conn = get_connection(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) AS n FROM circulars").fetchone()["n"]
        assert total == 2
    finally:
        conn.close()