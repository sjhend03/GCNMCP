import asyncio
import json
import sys
import types
from dataclasses import dataclass


@dataclass
class FakeTool:
    name: str
    description: str
    input_schema: dict


@dataclass
class FakeTextContext:
    text: str


fake_tool_module = types.ModuleType("Tool")
fake_tool_module.Tool = FakeTool
sys.modules["Tool"] = fake_tool_module

fake_textcontext_module = types.ModuleType("TextContext")
fake_textcontext_module.TextContext = FakeTextContext
sys.modules["TextContext"] = fake_textcontext_module

fake_ollama_module = types.ModuleType("ollama")
fake_ollama_module.chat = lambda *args, **kwargs: {"message": {"content": "{}"}}
sys.modules["ollama"] = fake_ollama_module


from src.indexer import ingest_path
import src.tools as tools


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


def build_test_data_dir(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    record1 = make_record(
        circular_id=10001,
        subject="GRB 260120B: test raw circular",
        body="This raw circular is about GRB 260120B and mentions redshift z = 1.23.",
        event_id="GRB 260120B",
        created_on=1769036892952,
    )
    record2 = make_record(
        circular_id=10002,
        subject="EP260119a: optical observations",
        body="This raw circular is about EP260119a.",
        event_id="EP260119a",
        created_on=1769036892953,
    )

    (data_dir / "a.json").write_text(json.dumps(record1), encoding="utf-8")
    (data_dir / "b.json").write_text(json.dumps(record2), encoding="utf-8")

    return data_dir


def test_list_tools_contains_expected_tool_names():
    tool_list = asyncio.run(tools.list_tools())
    names = {tool.name for tool in tool_list}

    assert "fetch_gcn_circulars" in names
    assert "search_gcn_circulars" in names
    assert "get_event_circulars" in names
    assert "get_gcn_circular" in names
    assert "fetch_and_check_circular_for_grb" in names
    assert "check_for_grb_regex" in names


def test_fetch_gcn_circulars_returns_raw_file_contents(tmp_path):
    data_dir = build_test_data_dir(tmp_path)

    results = asyncio.run(
        tools.call_tool(
            "fetch_gcn_circulars",
            {
                "data_dir": str(data_dir),
                "start_index": 0,
                "end_index": 1,
            },
        )
    )

    assert len(results) == 1
    assert "GRB 260120B: test raw circular" in results[0].text


def test_search_gcn_circulars_returns_text_contexts_from_index(tmp_path, monkeypatch):
    db_path = build_test_db(tmp_path)
    monkeypatch.setattr(tools, "DEFAULT_DB_PATH", str(db_path))

    results = asyncio.run(
        tools.call_tool(
            "search_gcn_circulars",
            {
                "query": "optical counterpart",
                "event": "EP260119a",
                "limit": 10,
            },
        )
    )

    assert len(results) >= 2
    assert "Circular ID:" in results[0].text
    assert "Primary event: EP260119a" in results[0].text or "Primary event: EP260119A" in results[0].text
    assert "Snippet:" in results[0].text


def test_search_gcn_circulars_returns_no_match_message_when_empty(tmp_path, monkeypatch):
    db_path = build_test_db(tmp_path)
    monkeypatch.setattr(tools, "DEFAULT_DB_PATH", str(db_path))

    results = asyncio.run(
        tools.call_tool(
            "search_gcn_circulars",
            {
                "query": "neutrino radio supernova fallback impossiblephrase",
                "event": "EP260119a",
                "limit": 10,
            },
        )
    )

    assert len(results) == 1
    assert results[0].text == "No matching circulars found."


def test_get_event_circulars_returns_event_cluster(tmp_path, monkeypatch):
    db_path = build_test_db(tmp_path)
    monkeypatch.setattr(tools, "DEFAULT_DB_PATH", str(db_path))

    results = asyncio.run(
        tools.call_tool(
            "get_event_circulars",
            {
                "event": "GRB 260120B",
                "limit": 10,
            },
        )
    )

    assert len(results) == 2
    assert all("Primary event: GRB 260120B" in r.text for r in results)


def test_get_event_circulars_returns_no_match_message_when_empty(tmp_path, monkeypatch):
    db_path = build_test_db(tmp_path)
    monkeypatch.setattr(tools, "DEFAULT_DB_PATH", str(db_path))

    results = asyncio.run(
        tools.call_tool(
            "get_event_circulars",
            {
                "event": "GRB 999999Z",
                "limit": 10,
            },
        )
    )

    assert len(results) == 1
    assert "No circulars found for event GRB 999999Z." == results[0].text


def test_get_gcn_circular_returns_full_circular(tmp_path, monkeypatch):
    db_path = build_test_db(tmp_path)
    monkeypatch.setattr(tools, "DEFAULT_DB_PATH", str(db_path))

    results = asyncio.run(
        tools.call_tool(
            "get_gcn_circular",
            {
                "circular_id": 43483,
            },
        )
    )

    assert len(results) == 1
    assert "Circular ID: 43483" in results[0].text
    assert "GRB 260120B: SVOM/C-GFT optical counterpart detection" in results[0].text
    assert "Body:" in results[0].text


def test_get_gcn_circular_returns_missing_message(tmp_path, monkeypatch):
    db_path = build_test_db(tmp_path)
    monkeypatch.setattr(tools, "DEFAULT_DB_PATH", str(db_path))

    results = asyncio.run(
        tools.call_tool(
            "get_gcn_circular",
            {
                "circular_id": 999999,
            },
        )
    )

    assert len(results) == 1
    assert results[0].text == "No circular found for circular_id=999999."


def test_check_for_grb_regex_returns_true_for_grb_subject(tmp_path):
    data_dir = build_test_data_dir(tmp_path)

    results = asyncio.run(
        tools.call_tool(
            "check_for_grb_regex",
            {
                "data_dir": str(data_dir),
                "index": 0,
            },
        )
    )

    payload = json.loads(results[0].text)
    assert payload["is_grb"] is True
    assert payload["match"] == "260120B"


def test_check_for_grb_regex_returns_false_for_non_grb_subject(tmp_path):
    data_dir = build_test_data_dir(tmp_path)

    results = asyncio.run(
        tools.call_tool(
            "check_for_grb_regex",
            {
                "data_dir": str(data_dir),
                "index": 1,
            },
        )
    )

    payload = json.loads(results[0].text)
    assert payload["is_grb"] is False
    assert payload["match"] is None


def test_check_for_grb_regex_handles_out_of_range_index(tmp_path):
    data_dir = build_test_data_dir(tmp_path)

    results = asyncio.run(
        tools.call_tool(
            "check_for_grb_regex",
            {
                "data_dir": str(data_dir),
                "index": 99,
            },
        )
    )

    payload = json.loads(results[0].text)
    assert "error" in payload
    assert "out of range" in payload["error"]


def test_fetch_and_check_circular_for_grb_parses_valid_ollama_json(tmp_path, monkeypatch):
    data_dir = build_test_data_dir(tmp_path)

    def fake_chat(model, messages):
        return {
            "message": {
                "content": json.dumps(
                    {
                        "is_grb": True,
                        "grb_name": "260120B",
                        "has_redshift": True,
                        "z": 1.23,
                        "z_err": None,
                        "confidence": 0.98,
                        "notes": "Detected GRB and redshift mention.",
                    }
                )
            }
        }

    monkeypatch.setattr(tools.ollama, "chat", fake_chat)

    results = asyncio.run(
        tools.call_tool(
            "fetch_and_check_circular_for_grb",
            {
                "data_dir": str(data_dir),
                "index": 0,
                "model": "fake-model",
            },
        )
    )

    payload = json.loads(results[0].text)
    assert payload["is_grb"] is True
    assert payload["grb_name"] == "260120B"
    assert payload["has_redshift"] is True
    assert payload["z"] == 1.23


def test_fetch_and_check_circular_for_grb_extracts_json_from_wrapped_output(tmp_path, monkeypatch):
    data_dir = build_test_data_dir(tmp_path)

    wrapped = """
Here is the result:

{
    "is_grb": true,
    "grb_name": "260120B",
    "has_redshift": false,
    "z": null,
    "z_err": null,
    "confidence": 0.91,
    "notes": "Looks like a GRB circular."
}
"""

    def fake_chat(model, messages):
        return {
            "message": {
                "content": wrapped
            }
        }

    monkeypatch.setattr(tools.ollama, "chat", fake_chat)

    results = asyncio.run(
        tools.call_tool(
            "fetch_and_check_circular_for_grb",
            {
                "data_dir": str(data_dir),
                "index": 0,
                "model": "fake-model",
            },
        )
    )

    payload = json.loads(results[0].text)
    assert payload["is_grb"] is True
    assert payload["grb_name"] == "260120B"
    assert payload["has_redshift"] is False


def test_fetch_and_check_circular_for_grb_returns_error_when_model_output_is_not_json(tmp_path, monkeypatch):
    data_dir = build_test_data_dir(tmp_path)

    def fake_chat(model, messages):
        return {
            "message": {
                "content": "This is not JSON at all."
            }
        }

    monkeypatch.setattr(tools.ollama, "chat", fake_chat)

    results = asyncio.run(
        tools.call_tool(
            "fetch_and_check_circular_for_grb",
            {
                "data_dir": str(data_dir),
                "index": 0,
                "model": "fake-model",
            },
        )
    )

    payload = json.loads(results[0].text)
    assert "error" in payload
    assert payload["error"] == "Could not parse model output as JSON"


def test_unknown_tool_returns_error():
    results = asyncio.run(
        tools.call_tool(
            "totally_unknown_tool",
            {},
        )
    )

    payload = json.loads(results[0].text)
    assert "error" in payload
    assert "Unknown tool" in payload["error"]