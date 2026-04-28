"""
tests/test_py_bridge.py — integration tests for leanmcp_bridge/py_bridge.py

py_bridge.py is the stdin/stdout subprocess that TypeScript calls.
These tests exercise it as a black box: write JSON to stdin, read JSON from stdout.

Covers:
  - Empty stdin → ok: false + error message
  - Non-JSON stdin → ok: false + error message
  - Missing "tool" field → ok: false + error message
  - ping_python → ok: true, result contains pong message
  - Unknown tool → ok: true, result contains error field (tools.py handles it)
  - fetch_gcn_circulars with real data dir → ok: true, result is a list
  - check_for_grb_regex on a GRB circular → ok: true, is_grb true
  - check_for_grb_regex out-of-range → ok: true, error in result
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

BRIDGE_SCRIPT = Path(__file__).resolve().parent.parent / "leanmcp_bridge" / "py_bridge.py"
PYTHON_BIN = sys.executable


def call_bridge(payload: str | None) -> dict:
    """Run py_bridge.py with the given stdin payload and return the parsed JSON output."""
    proc = subprocess.run(
        [PYTHON_BIN, str(BRIDGE_SCRIPT)],
        input=payload or "",
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.stdout.strip(), f"No stdout. Stderr: {proc.stderr}"
    return json.loads(proc.stdout.strip())


def make_payload(tool: str, arguments: dict | None = None) -> str:
    return json.dumps({"tool": tool, "arguments": arguments or {}})


def make_data_dir_with_records(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    grb_record = {
        "circularId": 10001,
        "subject": "GRB 260120B: Swift-BAT detection",
        "eventId": "GRB 260120B",
        "createdOn": 1_769_036_892_952,
        "submitter": "Test",
        "format": "text/plain",
        "body": "Detection of GRB 260120B by Swift-BAT.",
    }
    ep_record = {
        "circularId": 10002,
        "subject": "EP260119a: optical follow-up",
        "eventId": "EP260119a",
        "createdOn": 1_768_900_000_000,
        "submitter": "Test",
        "format": "text/plain",
        "body": "Optical follow-up of EP260119a.",
    }
    (data_dir / "10001.json").write_text(json.dumps(grb_record), encoding="utf-8")
    (data_dir / "10002.json").write_text(json.dumps(ep_record), encoding="utf-8")
    return data_dir


# ── error handling ────────────────────────────────────────────────────────────

def test_empty_stdin_returns_error():
    result = call_bridge("")
    assert result["ok"] is False
    assert "No input" in result["error"]


def test_non_json_stdin_returns_error():
    result = call_bridge("this is not json at all")
    assert result["ok"] is False
    assert "Invalid JSON" in result["error"]


def test_missing_tool_field_returns_error():
    result = call_bridge(json.dumps({"arguments": {}}))
    assert result["ok"] is False
    assert "tool" in result["error"]


def test_empty_tool_string_returns_error():
    result = call_bridge(json.dumps({"tool": "", "arguments": {}}))
    assert result["ok"] is False


# ── ping_python ───────────────────────────────────────────────────────────────

def test_ping_python_returns_ok_true():
    result = call_bridge(make_payload("ping_python"))
    assert result["ok"] is True


def test_ping_python_result_contains_pong():
    result = call_bridge(make_payload("ping_python"))
    result_items = result["result"]
    assert isinstance(result_items, list)
    assert len(result_items) == 1
    text_item = result_items[0]
    assert text_item["type"] == "text"
    inner = json.loads(text_item["text"])
    assert inner["message"] == "pong from python"


def test_ping_python_result_is_normalized_text_list():
    """Result items must be {type: text, text: ...} dicts — not raw TextContext objects."""
    result = call_bridge(make_payload("ping_python"))
    for item in result["result"]:
        assert "type" in item
        assert item["type"] == "text"
        assert "text" in item


# ── unknown tool ──────────────────────────────────────────────────────────────

def test_unknown_tool_returns_ok_true_with_error_in_result():
    """py_bridge succeeds (ok:true) — unknown-tool errors are surfaced inside result."""
    result = call_bridge(make_payload("definitely_not_a_real_tool"))
    assert result["ok"] is True
    texts = [item["text"] for item in result["result"]]
    combined = " ".join(texts)
    payload = json.loads(texts[0])
    assert "error" in payload
    assert "Unknown tool" in payload["error"]


# ── fetch_gcn_circulars ───────────────────────────────────────────────────────

def test_fetch_gcn_circulars_with_real_files(tmp_path):
    data_dir = make_data_dir_with_records(tmp_path)
    payload = make_payload("fetch_gcn_circulars", {
        "data_dir": str(data_dir),
        "start_index": 0,
        "end_index": 1,
    })
    result = call_bridge(payload)
    assert result["ok"] is True
    items = result["result"]
    assert len(items) == 1
    inner = json.loads(items[0]["text"])
    assert inner["circularId"] in (10001, 10002)


def test_fetch_gcn_circulars_returns_two_files(tmp_path):
    data_dir = make_data_dir_with_records(tmp_path)
    payload = make_payload("fetch_gcn_circulars", {
        "data_dir": str(data_dir),
        "start_index": 0,
        "end_index": 2,
    })
    result = call_bridge(payload)
    assert result["ok"] is True
    assert len(result["result"]) == 2


# ── check_for_grb_regex ───────────────────────────────────────────────────────

def test_check_for_grb_regex_grb_subject(tmp_path):
    data_dir = make_data_dir_with_records(tmp_path)
    payload = make_payload("check_for_grb_regex", {
        "data_dir": str(data_dir),
        "index": 0,
    })
    result = call_bridge(payload)
    assert result["ok"] is True
    inner = json.loads(result["result"][0]["text"])
    assert inner["is_grb"] is True
    assert inner["match"] == "260120B"


def test_check_for_grb_regex_non_grb_subject(tmp_path):
    data_dir = make_data_dir_with_records(tmp_path)
    payload = make_payload("check_for_grb_regex", {
        "data_dir": str(data_dir),
        "index": 1,
    })
    result = call_bridge(payload)
    assert result["ok"] is True
    inner = json.loads(result["result"][0]["text"])
    assert inner["is_grb"] is False


def test_check_for_grb_regex_out_of_range(tmp_path):
    data_dir = make_data_dir_with_records(tmp_path)
    payload = make_payload("check_for_grb_regex", {
        "data_dir": str(data_dir),
        "index": 999,
    })
    result = call_bridge(payload)
    assert result["ok"] is True
    inner = json.loads(result["result"][0]["text"])
    assert "error" in inner


# ── arguments field handling ──────────────────────────────────────────────────

def test_null_arguments_field_is_treated_as_empty_dict():
    """py_bridge.py should handle arguments: null gracefully."""
    payload_str = json.dumps({"tool": "ping_python", "arguments": None})
    result = call_bridge(payload_str)
    assert result["ok"] is True


def test_missing_arguments_field_defaults_to_empty():
    payload_str = json.dumps({"tool": "ping_python"})
    result = call_bridge(payload_str)
    assert result["ok"] is True
