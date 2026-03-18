import re
from typing import Any, Optional


EVENT_PATTERNS = [
    r"\b(GRB\s?\d{6}[A-Z]?)\b",
    r"\b(EP\s?\d+[A-Z]?)\b",
    r"\b(AT\s?\d+[A-Z]?)\b",
    r"\b(SN\s?\d+[A-Z]?)\b",
    r"\b(ICECUBE\s?-?\d+[A-Z]?)\b",
    r"\b(SWIFT\s?J\d+(?:\.\d+)?[+-]\d+(?:\.\d+)?)\b",
]

def clean_text(text: Optional[str]) -> str:
    """
    Normalize text into a safe string to use e.g. None becomes "", null bytes removed, whitespace trimmed.
    """
    if text is None:
        return ""
    return text.replace("\x00", " ").strip()

def normalize_event(event: Optional[str]) -> Optional[str]:
    """
    Convert an event name into a searchable form by normalizing everything to uppercase and removing whitespace.
    Returns None if the input is empty or None
    """
    if not event:
        return None
    return re.sub(r"\s+", "", event).upper()

def extract_matches(text: str) -> list[str]:
    """
    Find all event-like identifiers in a block of text.

    Returns normalized event names with dupes removed.
    """
    found = []

    for pattern in EVENT_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            raw = match.group(1)
            norm = normalize_event(raw)
            if norm:
                found.append((match.start(), norm))
    found.sort(key=lambda x: x[0])

    results = []
    seen = set()
    for _, norm in found:
        if norm not in seen:
            seen.add(norm)
            results.append(norm)
    return results

def extract_event_regex(record: dict[str, Any]) -> tuple[Optional[str], list[str], str]:
    """
    Extract the primary event from a circular record by:
    eventId field (if possible)
    subject
    body

    Returns:
        primary_event_raw: the best raw event string if found
        all_events: all events found
        source: one of the {"eventId", "subject", "body", "none}
    """
    event_id = clean_text(record.get("eventId"))
    if event_id:
        event_norm = normalize_event(event_id)
        return event_id, ([event_norm] if event_norm else []), "eventId"
    
    subject = clean_text(record.get("subject"))
    subject_matches = extract_matches(subject)
    if subject_matches:
        return subject_matches[0], subject_matches, "subject"
    
    body = clean_text(record.get("body"))
    body_matches = extract_matches(body)
    if body_matches:
        return body_matches[0], body_matches, "body"
    
    return None, [], "none"

def extract_event_from_query(query: str) -> Optional[str]:
    """
    Pulls an event directly out of the user's query
    """
    matches = extract_matches(query)
    return matches[0] if matches else None