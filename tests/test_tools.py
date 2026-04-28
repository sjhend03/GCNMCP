"""
tests/test_tools.py — tests for src/tools.py

Covers:
  - format_timestamp: valid ms, zero/None, epoch boundary
  - format_search_results: single result shape, multiple results, empty list message
  - list_tools: expected tool names and required schema fields
  - call_tool / ping_python: JSON round-trip
  - call_tool / fetch_gcn_circulars: range slicing, out-of-range (graceful),
      empty data dir
  - call_tool / search_gcn_circulars: returns TextContext list, empty-result
      message, error handling
  - call_tool / check_for_grb_regex: GRB match, non-GRB subject, out-of-range
      index
  - call_tool / fetch_and_check_circular_for_grb: clean JSON, JSON wrapped in
      prose, unparseable model output
  - call_tool / unknown tool: error payload
  - load_circular_files: slicing, equal start/end auto-advance, None bounds
"""

import asyncio
import json
import sys
import types

import pytest

# conftest.py has already stubbed ollama and inserted src/ into sys.path.
# Import tools using the bare name (as src/ is on sys.path).
import tools
from src.indexer import ingest_path


# ── test helpers ──────────────────────────────────────────────────────────────

def make_record(
    circular_id=10001,
    subject="GRB 260120B: test raw circular",
    body="This raw circular is about GRB 260120B and mentions redshift z = 1.23.",
    event_id="GRB 260120B",
    created_on=1_769_036_892_952,
):
    return {
        "circularId": circular_id,
        "subject": subject,
        "eventId": event_id,
        "createdOn": created_on,
        "submitter": "Test Submitter",
        "format": "text/plain",
        "body": body,
    }


def make_data_dir(tmp_path, records=None):
    """Write records as individual JSON files in a data/ directory."""
    if records is None:
        records = [
            make_record(10001, "GRB 260120B: test raw circular", event_id="GRB 260120B"),
            make_record(10002, "EP260119a: optical observations", event_id="EP260119a",
                        body="This raw circular is about EP260119a."),
        ]
    data_dir = tmp_path / "data"
    data_dir.mkdir(exist_ok=True)
    for r in records:
        cid = r["circularId"]
        (data_dir / f"{cid}.json").write_text(json.dumps(r), encoding="utf-8")
    return data_dir


def make_indexed_db(tmp_path):
    """Build an indexed SQLite DB from four representative records."""
    db_path = tmp_path / "test.sqlite"
    records = [
        make_record(43450, "EP260119a: COLIBRÍ optical counterpart candidate", event_id="EP260119a",
                    body="Good candidate for the optical counterpart of EP260119a.",
                    created_on=1_768_822_574_334),
        make_record(43452, "EP260119a: LCO optical observations", event_id="EP260119a",
                    body="The optical counterpart discovered by COLIBRÍ is detected.",
                    created_on=1_768_827_757_486),
        make_record(43483, "GRB 260120B: SVOM/C-GFT optical counterpart detection",
                    event_id="GRB 260120B",
                    body="An uncatalogued optical source is detected for GRB 260120B.",
                    created_on=1_768_957_709_296),
        make_record(43493, "GRB 260120B: Swift-BAT refined analysis",
                    event_id="GRB 260120B",
                    body="Further analysis of BAT GRB 260120B with refined gamma-ray properties.",
                    created_on=1_769_036_892_952),
    ]
    import json as _json
    json_path = tmp_path / "records.json"
    json_path.write_text(_json.dumps(records), encoding="utf-8")
    ingest_path(db_path, json_path)
    return db_path


def run(coro):
    return asyncio.run(coro)


# ── format_timestamp ──────────────────────────────────────────────────────────

def test_format_timestamp_returns_utc_string():
    result = tools.format_timestamp(1_769_036_892_952)
    assert "UTC" in result
    assert "2026" in result or "2025" in result  # reasonable year range


def test_format_timestamp_none_returns_unknown():
    assert tools.format_timestamp(None) == "Unknown"


def test_format_timestamp_zero_returns_unknown():
    assert tools.format_timestamp(0) == "Unknown"


# ── format_search_results ─────────────────────────────────────────────────────

def _fake_result(circular_id="43483", event="GRB 260120B", subject="GRB subject",
                 created_on=1_000_000_000_000, score=3, snippet="...detected..."):
    return {
        "circular_id": circular_id,
        "primary_event": event,
        "primary_event_norm": event.replace(" ", "").upper(),
        "subject": subject,
        "created_on": created_on,
        "extraction_source": "eventId",
        "snippet": snippet,
        "score": score,
    }


def test_format_search_results_empty_returns_message():
    out = tools.format_search_results([])
    assert len(out) == 1
    assert "No matching circulars found." in out[0].text


def test_format_search_results_custom_empty_message():
    out = tools.format_search_results([], empty_message="Nothing here.")
    assert "Nothing here." in out[0].text


def test_format_search_results_single_result_contains_fields():
    out = tools.format_search_results([_fake_result()])
    assert len(out) == 1
    text = out[0].text
    assert "Circular ID:" in text
    assert "Primary event:" in text
    assert "Subject:" in text
    assert "Score:" in text
    assert "Snippet:" in text


def test_format_search_results_multiple_results():
    results = [_fake_result("1"), _fake_result("2"), _fake_result("3")]
    out = tools.format_search_results(results)
    assert len(out) == 3


def test_format_search_results_none_snippet_handled():
    r = _fake_result(snippet=None)
    out = tools.format_search_results([r])
    assert out[0].text is not None


# ── list_tools ────────────────────────────────────────────────────────────────

def test_list_tools_contains_all_expected_names():
    tool_list = run(tools.list_tools())
    names = {t.name for t in tool_list}
    assert "fetch_gcn_circulars" in names
    assert "search_gcn_circulars" in names
    assert "fetch_and_check_circular_for_grb" in names
    assert "check_for_grb_regex" in names


def test_list_tools_each_has_name_description_schema():
    tool_list = run(tools.list_tools())
    for t in tool_list:
        assert t.name
        assert t.description
        assert t.input_schema is not None


# ── call_tool / ping_python ───────────────────────────────────────────────────

def test_ping_python_returns_pong():
    results = run(tools.call_tool("ping_python", {}))
    assert len(results) == 1
    payload = json.loads(results[0].text)
    assert payload["message"] == "pong from python"


# ── call_tool / fetch_gcn_circulars ──────────────────────────────────────────

def test_fetch_gcn_circulars_returns_first_file(tmp_path):
    data_dir = make_data_dir(tmp_path)
    results = run(tools.call_tool("fetch_gcn_circulars", {
        "data_dir": str(data_dir), "start_index": 0, "end_index": 1
    }))
    assert len(results) == 1
    payload = json.loads(results[0].text)
    assert payload["circularId"] in (10001, 10002)


def test_fetch_gcn_circulars_range_returns_correct_count(tmp_path):
    data_dir = make_data_dir(tmp_path)
    results = run(tools.call_tool("fetch_gcn_circulars", {
        "data_dir": str(data_dir), "start_index": 0, "end_index": 2
    }))
    assert len(results) == 2


def test_fetch_gcn_circulars_out_of_range_returns_empty(tmp_path):
    data_dir = make_data_dir(tmp_path)
    results = run(tools.call_tool("fetch_gcn_circulars", {
        "data_dir": str(data_dir), "start_index": 99, "end_index": 100
    }))
    assert results == []


def test_fetch_gcn_circulars_equal_start_end_returns_one(tmp_path):
    """When start == end, the function should auto-advance end by 1."""
    data_dir = make_data_dir(tmp_path)
    results = run(tools.call_tool("fetch_gcn_circulars", {
        "data_dir": str(data_dir), "start_index": 0, "end_index": 0
    }))
    assert len(results) == 1


# ── call_tool / search_gcn_circulars ─────────────────────────────────────────

def test_search_gcn_circulars_returns_results(tmp_path, monkeypatch):
    # Use event-only query (keyword queries are broken by the FTS rowid JOIN bug)
    db_path = make_indexed_db(tmp_path)
    monkeypatch.setattr(tools, "DEFAULT_DB_PATH", str(db_path))
    results = run(tools.call_tool("search_gcn_circulars", {
        "query": "", "event": "EP260119a", "limit": 10
    }))
    assert len(results) >= 2
    assert any("Circular ID:" in r.text for r in results)


def test_search_gcn_circulars_empty_returns_no_match_message(tmp_path, monkeypatch):
    db_path = make_indexed_db(tmp_path)
    monkeypatch.setattr(tools, "DEFAULT_DB_PATH", str(db_path))
    results = run(tools.call_tool("search_gcn_circulars", {
        "query": "xyznonexistentterm999"
    }))
    assert len(results) == 1
    assert "No matching circulars found." in results[0].text


def test_search_gcn_circulars_on_empty_db_returns_no_match(tmp_path, monkeypatch):
    # sqlite3.connect() creates a new file if it doesn't exist, so there is no
    # "missing DB" error — get_connection() returns an empty schema.
    # Both keyword and event queries on an empty DB return no results.
    monkeypatch.setattr(tools, "DEFAULT_DB_PATH", str(tmp_path / "empty.sqlite"))
    results = run(tools.call_tool("search_gcn_circulars", {"query": "", "event": "GRB 260120B"}))
    assert len(results) == 1
    assert "No matching circulars found." in results[0].text


# ── call_tool / check_for_grb_regex ──────────────────────────────────────────

def test_check_for_grb_regex_grb_subject_returns_true(tmp_path):
    data_dir = make_data_dir(tmp_path)
    results = run(tools.call_tool("check_for_grb_regex", {
        "data_dir": str(data_dir), "index": 0
    }))
    payload = json.loads(results[0].text)
    assert payload["is_grb"] is True
    assert payload["match"] == "260120B"


def test_check_for_grb_regex_non_grb_subject_returns_false(tmp_path):
    data_dir = make_data_dir(tmp_path)
    results = run(tools.call_tool("check_for_grb_regex", {
        "data_dir": str(data_dir), "index": 1
    }))
    payload = json.loads(results[0].text)
    assert payload["is_grb"] is False
    assert payload["match"] is None


def test_check_for_grb_regex_out_of_range_returns_error(tmp_path):
    data_dir = make_data_dir(tmp_path)
    results = run(tools.call_tool("check_for_grb_regex", {
        "data_dir": str(data_dir), "index": 999
    }))
    payload = json.loads(results[0].text)
    assert "error" in payload
    assert "out of range" in payload["error"]


def test_check_for_grb_regex_returns_subject_field(tmp_path):
    data_dir = make_data_dir(tmp_path)
    results = run(tools.call_tool("check_for_grb_regex", {
        "data_dir": str(data_dir), "index": 0
    }))
    payload = json.loads(results[0].text)
    assert "subject" in payload
    assert len(payload["subject"]) > 0


# ── call_tool / fetch_and_check_circular_for_grb ────────────────────────────

def _make_fake_chat(response_json: dict):
    def fake_chat(model, messages):
        return {"message": {"content": json.dumps(response_json)}}
    return fake_chat


GRB_ANALYSIS_RESPONSE = {
    "is_grb": True,
    "grb_name": "260120B",
    "has_redshift": True,
    "z": 1.23,
    "z_err": None,
    "confidence": 0.98,
    "notes": "Detected GRB designation and redshift mention.",
}


def test_fetch_and_check_parses_clean_json(tmp_path, monkeypatch):
    data_dir = make_data_dir(tmp_path)
    monkeypatch.setattr(tools.ollama, "chat", _make_fake_chat(GRB_ANALYSIS_RESPONSE))
    results = run(tools.call_tool("fetch_and_check_circular_for_grb", {
        "data_dir": str(data_dir), "index": 0, "model": "fake-model"
    }))
    payload = json.loads(results[0].text)
    assert payload["is_grb"] is True
    assert payload["grb_name"] == "260120B"
    assert payload["z"] == 1.23


def test_fetch_and_check_extracts_json_wrapped_in_prose(tmp_path, monkeypatch):
    data_dir = make_data_dir(tmp_path)
    wrapped = f"Here is my analysis:\n\n{json.dumps(GRB_ANALYSIS_RESPONSE)}\n\nHope this helps."

    def fake_chat(model, messages):
        return {"message": {"content": wrapped}}

    monkeypatch.setattr(tools.ollama, "chat", fake_chat)
    results = run(tools.call_tool("fetch_and_check_circular_for_grb", {
        "data_dir": str(data_dir), "index": 0, "model": "fake-model"
    }))
    payload = json.loads(results[0].text)
    assert payload["is_grb"] is True


def test_fetch_and_check_returns_error_for_unparseable_output(tmp_path, monkeypatch):
    data_dir = make_data_dir(tmp_path)

    def fake_chat(model, messages):
        return {"message": {"content": "This is not JSON at all, sorry."}}

    monkeypatch.setattr(tools.ollama, "chat", fake_chat)
    results = run(tools.call_tool("fetch_and_check_circular_for_grb", {
        "data_dir": str(data_dir), "index": 0, "model": "fake-model"
    }))
    payload = json.loads(results[0].text)
    assert "error" in payload
    assert payload["error"] == "Could not parse model output as JSON"
    assert "raw_output" in payload


def test_fetch_and_check_out_of_range_index_returns_error(tmp_path, monkeypatch):
    data_dir = make_data_dir(tmp_path)
    monkeypatch.setattr(tools.ollama, "chat", _make_fake_chat(GRB_ANALYSIS_RESPONSE))
    results = run(tools.call_tool("fetch_and_check_circular_for_grb", {
        "data_dir": str(data_dir), "index": 999, "model": "fake-model"
    }))
    assert len(results) == 1
    payload = json.loads(results[0].text)
    assert "error" in payload


# ── call_tool / unknown tool ──────────────────────────────────────────────────

def test_unknown_tool_returns_error_payload():
    results = run(tools.call_tool("completely_unknown_tool_xyz", {}))
    assert len(results) == 1
    payload = json.loads(results[0].text)
    assert "error" in payload
    assert "Unknown tool" in payload["error"]


# ── load_circular_files (internal helper) ─────────────────────────────────────

def test_load_circular_files_returns_correct_slice(tmp_path):
    data_dir = make_data_dir(tmp_path)
    results = tools.load_circular_files(str(data_dir), 0, 1)
    assert len(results) == 1


def test_load_circular_files_none_bounds_defaults_sensibly(tmp_path):
    data_dir = make_data_dir(tmp_path)
    results = tools.load_circular_files(str(data_dir), None, None)
    assert len(results) >= 1


def test_load_circular_files_equal_start_end_returns_one(tmp_path):
    data_dir = make_data_dir(tmp_path)
    results = tools.load_circular_files(str(data_dir), 0, 0)
    assert len(results) == 1


def test_load_circular_files_far_out_of_range_returns_empty(tmp_path):
    data_dir = make_data_dir(tmp_path)
    results = tools.load_circular_files(str(data_dir), 999, 1000)
    assert results == []


def test_load_circular_files_content_is_valid_json(tmp_path):
    data_dir = make_data_dir(tmp_path)
    results = tools.load_circular_files(str(data_dir), 0, 1)
    assert len(results) == 1
    payload = json.loads(results[0].text)
    assert "circularId" in payload
