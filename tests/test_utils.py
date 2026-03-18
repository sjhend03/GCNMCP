import pytest

from src.utils import (
    clean_text,
    normalize_event,
    extract_matches,
    extract_event_regex,
    extract_event_from_query,
)


def test_clean_text_none_returns_empty_string():
    assert clean_text(None) == ""


def test_clean_text_strips_whitespace_and_null_bytes():
    assert clean_text("  GRB 260120B\x00  ") == "GRB 260120B"


def test_normalize_event_removes_spaces_and_uppercases():
    assert normalize_event("GRB 260120B") == "GRB260120B"
    assert normalize_event("ep260119a") == "EP260119A"


def test_normalize_event_none_returns_none():
    assert normalize_event(None) is None
    assert normalize_event("") is None


def test_extract_matches_finds_multiple_events_in_order():
    text = "We observed GRB 260120B and compared it with EP260119a and GRB250101A."
    assert extract_matches(text) == ["GRB260120B", "EP260119A", "GRB250101A"]       

def test_extract_matches_removes_duplicates():
    text = "GRB 260120B was detected. Later GRB260120B was analyzed again."
    assert extract_matches(text) == ["GRB260120B"]


def test_extract_matches_returns_empty_list_when_no_event_found():
    text = "We observed the field and found no significant uncatalogued source."
    assert extract_matches(text) == []


def test_extract_event_regex_prefers_event_id():
    record = {
        "eventId": "GRB 260120B",
        "subject": "EP260119a: optical observations",
        "body": "Body mentions AT2025abc"
    }

    primary_event, all_events, source = extract_event_regex(record)

    assert primary_event == "GRB 260120B"
    assert all_events == ["GRB260120B"]
    assert source == "eventId"


def test_extract_event_regex_uses_subject_when_event_id_missing():
    record = {
        "eventId": None,
        "subject": "EP260119a: COLIBRÍ optical counterpart candidate",
        "body": "The source is a good candidate counterpart."
    }

    primary_event, all_events, source = extract_event_regex(record)

    assert primary_event == "EP260119A"
    assert all_events == ["EP260119A"]
    assert source == "subject"


def test_extract_event_regex_uses_body_when_subject_missing_event():
    record = {
        "eventId": None,
        "subject": "Optical observations",
        "body": "We observed the field of GRB 260120B and measured its afterglow."
    }

    primary_event, all_events, source = extract_event_regex(record)

    assert primary_event == "GRB260120B"
    assert all_events == ["GRB260120B"]
    assert source == "body"


def test_extract_event_regex_returns_none_when_no_event_found():
    record = {
        "eventId": None,
        "subject": "Optical observations",
        "body": "We observed the field and found no transient."
    }

    primary_event, all_events, source = extract_event_regex(record)

    assert primary_event is None
    assert all_events == []
    assert source == "none"


def test_extract_event_regex_finds_multiple_body_events():
    record = {
        "eventId": None,
        "subject": "Follow-up report",
        "body": "We observed GRB 260120B and compared it with EP260119a."
    }

    primary_event, all_events, source = extract_event_regex(record)

    assert primary_event == "GRB260120B"
    assert all_events == ["GRB260120B", "EP260119A"]
    assert source == "body"


def test_extract_event_from_query_returns_first_event():
    query = "Find optical counterpart reports for EP260119a and compare with GRB 260120B"
    assert extract_event_from_query(query) == "EP260119A"


def test_extract_event_from_query_returns_none_when_missing():
    query = "Find optical counterpart reports with redshift measurements"
    assert extract_event_from_query(query) is None