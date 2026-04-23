import json
import hashlib
from pathlib import Path
from decimal import Decimal, InvalidOperation
from typing import Any
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.db import get_connection


def parse_circular_id(value: Any) -> tuple[str | None, int | None]:
    """
    Returns:
      circular_id_raw: exact normalized string form
      circular_id_int: integer value if the ID is a true integer, else None
    """
    if value is None:
        return None, None

    if isinstance(value, int):
        return str(value), value

    if isinstance(value, float):
        raw = format(value, "g")
        if value.is_integer():
            return str(int(value)), int(value)
        return raw, None

    text = str(value).strip()
    if not text:
        return None, None

    try:
        dec = Decimal(text)
    except (InvalidOperation, ValueError):
        return text, None

    if dec == dec.to_integral_value():
        return str(int(dec)), int(dec)

    return text, None


def sha1_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()


def make_record_hash(record: dict[str, Any]) -> str:
    return sha1_text(json.dumps(record, sort_keys=True, ensure_ascii=False))


def iter_raw_files(input_path: str | Path):
    path = Path(input_path)

    if path.is_file():
        yield path
        return

    for child in sorted(path.rglob("*.json")):
        yield child
    for child in sorted(path.rglob("*.jsonl")):
        yield child


def iter_records_with_source(input_path: str | Path):
    for path in iter_raw_files(input_path):
        if path.suffix.lower() == ".json":
            try:
                with path.open("r", encoding="utf-8") as f:
                    payload = json.load(f)

                if isinstance(payload, list):
                    for i, record in enumerate(payload):
                        yield {
                            "source_file": str(path),
                            "source_index": i,
                            "record": record,
                        }
                elif isinstance(payload, dict):
                    yield {
                        "source_file": str(path),
                        "source_index": 0,
                        "record": payload,
                    }
                else:
                    yield {
                        "source_file": str(path),
                        "source_index": None,
                        "error": f"Unsupported JSON payload type: {type(payload).__name__}",
                    }
            except Exception as e:
                yield {
                    "source_file": str(path),
                    "source_index": None,
                    "error": f"JSON parse error: {e}",
                }

        elif path.suffix.lower() == ".jsonl":
            try:
                with path.open("r", encoding="utf-8") as f:
                    for i, line in enumerate(f):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                            yield {
                                "source_file": str(path),
                                "source_index": i,
                                "record": record,
                            }
                        except Exception as e:
                            yield {
                                "source_file": str(path),
                                "source_index": i,
                                "error": f"JSONL parse error: {e}",
                            }
            except Exception as e:
                yield {
                    "source_file": str(path),
                    "source_index": None,
                    "error": f"JSONL open/read error: {e}",
                }


def validate_index(db_path: str | Path, input_path: str | Path) -> dict[str, Any]:
    conn = get_connection(db_path)

    report: dict[str, Any] = {
        "total_raw_records": 0,
        "bad_json_records": [],
        "missing_circular_id": [],
        "duplicate_circular_ids": {},
        "missing_from_db": [],
        "hash_mismatches": [],
        "missing_fts_rows": [],
        "missing_event_rows": [],
        "db_rows_without_raw_file_match": [],
        "summary": {},
    }

    seen_ids: dict[str, list[dict[str, Any]]] = {}
    raw_ids: set[str] = set()

    for item in iter_records_with_source(input_path):
        if "error" in item:
            report["bad_json_records"].append(item)
            continue

        report["total_raw_records"] += 1
        record = item["record"]

        circular_id_raw, circular_id_int = parse_circular_id(record.get("circularId"))

        if circular_id_raw is None:
            report["missing_circular_id"].append({
                "source_file": item["source_file"],
                "source_index": item["source_index"],
                "subject": record.get("subject"),
            })
            continue

        raw_ids.add(circular_id_raw)
        seen_ids.setdefault(circular_id_raw, []).append(item)

        db_row = conn.execute(
            """
            SELECT circular_id_raw, circular_id_int, record_hash
            FROM circulars
            WHERE circular_id_raw = ?
            """,
            (circular_id_raw,),
        ).fetchone()

        if db_row is None:
            report["missing_from_db"].append({
                "circular_id_raw": circular_id_raw,
                "circular_id_int": circular_id_int,
                "source_file": item["source_file"],
                "source_index": item["source_index"],
                "subject": record.get("subject"),
            })
            continue

        raw_hash = make_record_hash(record)
        if db_row["record_hash"] != raw_hash:
            report["hash_mismatches"].append({
                "circular_id_raw": circular_id_raw,
                "circular_id_int": circular_id_int,
                "source_file": item["source_file"],
                "source_index": item["source_index"],
                "db_hash": db_row["record_hash"],
                "raw_hash": raw_hash,
            })

        fts_row = conn.execute(
            "SELECT 1 FROM circulars_fts WHERE circular_id_raw = ? LIMIT 1",
            (circular_id_raw,),
        ).fetchone()
        if fts_row is None:
            report["missing_fts_rows"].append({
                "circular_id_raw": circular_id_raw,
                "circular_id_int": circular_id_int,
                "source_file": item["source_file"],
            })

    for circular_id_raw, items in seen_ids.items():
        if len(items) > 1:
            report["duplicate_circular_ids"][circular_id_raw] = [
                {
                    "source_file": x["source_file"],
                    "source_index": x["source_index"],
                }
                for x in items
            ]

    db_ids = {
        row["circular_id_raw"]
        for row in conn.execute("SELECT circular_id_raw FROM circulars")
    }

    extra_db_ids = sorted(db_ids - raw_ids)
    for circular_id_raw in extra_db_ids:
        row = conn.execute(
            """
            SELECT circular_id_raw, circular_id_int, subject, primary_event_norm
            FROM circulars
            WHERE circular_id_raw = ?
            """,
            (circular_id_raw,),
        ).fetchone()
        report["db_rows_without_raw_file_match"].append(dict(row))

    report["summary"] = {
        "total_raw_records": report["total_raw_records"],
        "bad_json_records_count": len(report["bad_json_records"]),
        "missing_circular_id_count": len(report["missing_circular_id"]),
        "duplicate_circular_id_count": len(report["duplicate_circular_ids"]),
        "missing_from_db_count": len(report["missing_from_db"]),
        "hash_mismatch_count": len(report["hash_mismatches"]),
        "missing_fts_rows_count": len(report["missing_fts_rows"]),
        "missing_event_rows_count": len(report["missing_event_rows"]),
        "db_rows_without_raw_file_match_count": len(report["db_rows_without_raw_file_match"]),
        "raw_id_count": len(raw_ids),
        "db_id_count": len(db_ids),
    }

    conn.close()
    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, help="Path to sqlite db")
    parser.add_argument("--input", required=True, help="Path to raw JSON/JSONL file or directory")
    parser.add_argument("--output", default=None, help="Optional path to write JSON report")
    args = parser.parse_args()

    report = validate_index(args.db, args.input)

    if args.output:
        Path(args.output).write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"Wrote report to {args.output}")
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))