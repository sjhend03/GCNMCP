import json
import hashlib
from pathlib import Path
from typing import Any, Iterable

from db import get_connection
from utils import clean_text, normalize_event, extract_event_regex

def sha1_text(text: str) -> str:
    """
    Returns a SHA1 hash of the input string.
    """
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()

def upsert_circular(conn, record: dict[str, Any]) -> None:
    """
    Insert or update a circular record.
    """
    circular_id = int(record["circularId"])
    subject = clean_text(record.get("subject"))
    body = clean_text(record.get("body"))
    created_on = record.get("createdOn")
    submitter = clean_text(record.get("submitter"))
    fmt = clean_text(record.get("format"))
    raw_event_id = clean_text(record.get("eventId")) or None

    record_hash = sha1_text(json.dumps(record, sort_keys=True, ensure_ascii=False))

    existing = conn.execute(
        "SELECT record_hash FROM circulars WHERE circular_id = ?",
        (circular_id,),
    ).fetchone()

    if existing and existing["record_hash"] == record_hash:
        return
    
    primary_event_raw, all_events, extraction_source = extract_event_regex(record)
    primary_event_norm = normalize_event(primary_event_raw)

    if primary_event_norm and primary_event_norm not in all_events:
        all_events.insert(0, primary_event_norm)

    conn.execute(
        """
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
        ON CONFLICT(circular_id) DO UPDATE SET
            subject=excluded.subject,
            body=excluded.body,
            created_on=excluded.created_on,
            submitter=excluded.submitter,
            format=excluded.format,
            raw_event_id=excluded.raw_event_id,
            primary_event_raw=excluded.primary_event_raw,
            primary_event_norm=excluded.primary_event_norm,
            extraction_source=excluded.extraction_source,
            llm_confidence=excluded.llm_confidence,
            record_hash=excluded.record_hash
        """
        ,
        (
            circular_id,
            subject,
            body,
            created_on,
            submitter,
            fmt,
            raw_event_id,
            primary_event_raw,
            primary_event_norm,
            extraction_source,
            None,
            record_hash
        ),
    )

    conn.execute("DELETE FROM circular_events WHERE circular_id = ?", (circular_id,))
    for event_norm in all_events:
        conn.execute(
            """
            INSERT OR IGNORE INTO circular_events (circular_id, event_norm, is_primary)
            VALUES (?, ?, ?)
            """,
            (
                circular_id,
                event_norm,
                1 if event_norm == primary_event_norm else 0,
            ),
        )
    conn.execute("DELETE FROM circulars_fts WHERE rowid = ?", (circular_id,))
    conn.execute(
        """
        INSERT INTO circulars_fts (rowid, subject, body)
        VALUES (?, ?, ?)
        """,
        (
            circular_id,
            subject,
            body
        ),
    )

def iter_json_records(input_path: str | Path) -> Iterable[dict[str, Any]]:
    """
    Gets records from json file or directory.
    """
    path = Path(input_path)

    if path.is_file():
        if path.suffix.lower() == ".jsonl":
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        yield json.loads(line)
        elif path.suffix.lower() == ".json":
            with path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
                if isinstance(payload, list):
                    for record in payload:
                        yield record
                elif isinstance(payload, dict):
                    yield payload
                else:
                    raise ValueError(f"Unsupported JSON paload in {input_path}")
        else:
            raise ValueError(f"Unsupported file type: {path}")
        
    elif path.is_dir():
        for child in sorted(path.rglob("*.json")):
            with child.open("r", encoding="utf-8") as f:
                yield json.load(f)

        for child in sorted(path.rglob("*.jsonl")):
            with child.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        yield json.loads(line)
    else:
        raise FileNotFoundError(input_path)
    
def ingest_path(db_path: str | Path, input_path: str | Path) -> int:
    """
    Ingests all records form input_path into the databse.
    Returns number of records ingested.
    """
    connection = get_connection(db_path)
    count = 0

    with connection:
        for record in iter_json_records(input_path):
            upsert_circular(connection, record)
            count += 1

    connection.close()
    return count
