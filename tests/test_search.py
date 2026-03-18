import json

from src.indexer import ingest_path
from src.search import (
    search_circulars,
    get_event_circulars,
    get_circular,
    parse_fts_terms,
)


def make_record(
    circular_id: int,
    subject: str,
    body: str,
    event_id: str | None,
    created_on: int,
):
    return {
        "subject": subject,
        "eventId": event_id,
        "submittedHow": "web",
        "createdOn": created_on,
        "circularId": circular_id,
        "submitter": "Test Submitter",
        "format": "text/plain",
        "body": body,
    }


def build_test_db(tmp_path):
    db_path = tmp_path / "test.sqlite"
    json_path = tmp_path / "records.json"

    records = [
        make_record(
            circular_id=43450,
            subject="EP260119a: COLIBRÍ optical counterpart candidate",
            body="The source is a good candidate for being the optical counterpart of EP260119a.",
            event_id="EP260119a",
            created_on=1768822574334,
        ),
        make_record(
            circular_id=43452,
            subject="EP260119a: LCO optical observations",
            body="The optical counterpart discovered by COLIBRÍ is detected in our images.",
            event_id="EP260119a",
            created_on=1768827757486,
        ),
        make_record(
            circular_id=43469,
            subject="EP260119A: GTC/OSIRIS+ spectroscopic redshift z = 5.47",
            body="We observed the optical counterpart and report a spectroscopic redshift.",
            event_id="EP260119a",
            created_on=1768902318897,
        ),
        make_record(
            circular_id=43483,
            subject="GRB 260120B: SVOM/C-GFT optical counterpart detection",
            body="An uncatalogued optical source is detected for GRB 260120B.",
            event_id="GRB 260120B",
            created_on=1768957709296,
        ),
        make_record(
            circular_id=43493,
            subject="GRB 260120B: Swift-BAT refined analysis",
            body="Further analysis of BAT GRB 260120B with refined gamma-ray properties.",
            event_id="GRB 260120B",
            created_on=1769036892952,
        ),
    ]

    json_path.write_text(json.dumps(records), encoding="utf-8")
    ingest_path(db_path, json_path)
    return db_path


def test_parse_fts_terms_joins_terms_with_and():
    assert parse_fts_terms("optical counterpart") == "optical AND counterpart"


def test_parse_fts_terms_returns_empty_phrase_for_no_valid_terms():
    assert parse_fts_terms("") == '""'


def test_search_circulars_keyword_only_returns_matches(tmp_path):
    db_path = build_test_db(tmp_path)

    results = search_circulars(db_path=db_path, query="optical counterpart", limit=10)

    assert len(results) >= 3
    subjects = [r["subject"] for r in results]
    assert "EP260119a: COLIBRÍ optical counterpart candidate" in subjects
    assert "GRB 260120B: SVOM/C-GFT optical counterpart detection" in subjects


def test_search_circulars_event_only_returns_event_cluster(tmp_path):
    db_path = build_test_db(tmp_path)

    results = search_circulars(db_path=db_path, event="EP260119a", limit=10)

    assert len(results) == 3
    assert all(r["primary_event_norm"] == "EP260119A" for r in results)


def test_search_circulars_keyword_and_event_filters_correctly(tmp_path):
    db_path = build_test_db(tmp_path)

    results = search_circulars(
        db_path=db_path,
        query="optical counterpart",
        event="EP260119a",
        limit=10,
    )

    assert len(results) == 3
    assert all(r["primary_event_norm"] == "EP260119A" for r in results)


def test_search_circulars_returns_results_sorted_by_recency_for_same_score(tmp_path):
    db_path = build_test_db(tmp_path)

    results = search_circulars(db_path=db_path, event="EP260119a", limit=10)

    circular_ids = [r["circular_id"] for r in results]
    assert circular_ids == [43469, 43452, 43450]


def test_search_circulars_assigns_score_3_to_exact_primary_event_matches(tmp_path):
    db_path = build_test_db(tmp_path)

    results = search_circulars(db_path=db_path, event="GRB 260120B", limit=10)

    assert len(results) == 2
    assert all(r["score"] == 3 for r in results)


def test_get_event_circulars_returns_only_requested_event(tmp_path):
    db_path = build_test_db(tmp_path)

    results = get_event_circulars(db_path=db_path, event="GRB 260120B", limit=10)

    assert len(results) == 2
    assert all(r["primary_event_norm"] == "GRB260120B" for r in results)


def test_get_circular_returns_full_record(tmp_path):
    db_path = build_test_db(tmp_path)

    result = get_circular(db_path=db_path, circular_id=43483)

    assert result is not None
    assert result["circular_id"] == 43483
    assert result["primary_event_norm"] == "GRB260120B"
    assert result["subject"] == "GRB 260120B: SVOM/C-GFT optical counterpart detection"
    assert "optical source is detected" in result["snippet"]


def test_get_circular_returns_none_for_missing_id(tmp_path):
    db_path = build_test_db(tmp_path)

    result = get_circular(db_path=db_path, circular_id=999999)

    assert result is None


def test_search_circulars_can_infer_event_from_query(tmp_path):
    db_path = build_test_db(tmp_path)

    results = search_circulars(
        db_path=db_path,
        query="optical counterpart reports for EP260119a",
        limit=10,
    )

    assert len(results) == 3
    assert all(r["primary_event_norm"] == "EP260119A" for r in results)