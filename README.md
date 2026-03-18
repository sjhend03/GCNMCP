# GCNMCP

An MCP (Model Context Protocol) agent for processing GCN (General Coordinates Network) circulars, extracting Gamma-Ray Burst (GRB) data with a local LLM, and searching an indexed database of GCN circulars by event or keyword.

---

## Overview

GCNMCP is a CLI-based AI agent that connects to a local MCP server to fetch and analyze GCN circulars.

It now supports two complementary workflows:

1. **Raw circular inspection**
   - Load local GCN JSON files directly by file index
   - Run regex or Ollama-based checks for GRB and redshift content

2. **Indexed circular search**
   - Ingest GCN circular JSON files into a local SQLite database
   - Extract event identifiers such as `GRB 260120B` or `EP260119a`
   - Build a fast full-text search index using SQLite FTS5
   - Search circulars by:
     - keyword
     - event
     - keyword + event
   - Retrieve all circulars associated with a given event
   - Retrieve a specific circular by circular ID

This makes the project useful both for exploratory file-based inspection and for fast retrieval over large circular collections.

---

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com/) with the `mistral` model pulled
- GCN circular JSON files in a `./data` directory
- SQLite with FTS5 support (included in standard Python builds on most systems)

---

## Setup & Installation

**1. Clone the repository**
```bash
git clone https://github.com/sjhend03/GCNMCP.git
cd GCNMCP
```

**2. Create and activate a virtual environment**
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Pull the Mistral model via Ollama**
```bash
ollama pull mistral
```

**5. Add GCN circular JSON files to the data directory**
```text
GCNMCP/
├── data/
│   ├── 00001.json
│   ├── 00002.json
│   └── ...
└── src/
```

Each circular JSON file should follow the GCN circular format and should ideally include fields such as:

- `circularId`
- `subject`
- `body`
- `createdOn`
- `eventId` (optional)
- `submitter` (optional)
- `format` (optional)

Example:
```json
{
  "subject": "GRB 260120B: Swift-BAT refined analysis",
  "eventId": "GRB 260120B",
  "createdOn": 1769036892952,
  "circularId": 43493,
  "submitter": "D. R. Sadaula at NASA GSFC <dev.r.sadaula@nasa.gov>",
  "format": "text/plain",
  "body": "Using the data set from T-769 to T+303 sec..."
}
```

---

## Project Structure

```text
GCNMCP/
├── data/                  # Raw GCN circular JSON files
├── gcn.sqlite             # Local SQLite search index
├── tests/                 # Unit tests
├── src/
│   ├── cli.py
│   ├── server.py
│   ├── tools.py
│   ├── utils.py           # Regex/event parsing helpers
│   ├── db.py              # SQLite schema + connection logic
│   ├── indexer.py         # Ingestion/upsert logic
│   ├── search.py          # Indexed retrieval functions
│   └── ...
└── README.md
```

---

## Indexed Search Pipeline

GCNMCP now includes a local indexing pipeline for fast search over large GCN collections.

### What the indexer does

- Reads circular JSON or JSONL files from `data/`
- Extracts event IDs using:
  1. `eventId`
  2. subject line regex matching
  3. body regex matching
- Normalizes event names into a canonical form:
  - `GRB 260120B` → `GRB260120B`
  - `EP260119a` → `EP260119A`
- Stores records in SQLite
- Stores event associations in a separate `circular_events` table
- Builds a full-text search table (`circulars_fts`) for fast keyword search

### Database features

- Exact event lookup
- Multi-event association per circular
- Full-text search over subject and body
- Incremental updates using record hashes
- Ranking of exact event matches over generic text matches

---

## Building / Rebuilding the Index

If you want to ingest or rebuild the local search index from the raw JSON files, run:

```bash
python -c "import sys; sys.path.append('src'); from indexer import ingest_path; print(ingest_path('gcn.sqlite', 'data'))"
```

This will read all supported JSON/JSONL records from `./data` and populate `gcn.sqlite`.

---

## Usage

### Start the MCP server
```bash
python src/server.py
```

### Start the CLI agent
```bash
python src/cli.py
```

---

## Example Interactions

### Fetch and preview circulars by index range
```text
> fetch circulars 0 to 5
```

### Analyze a specific circular for GRB content
```text
> check circular at index 10 for GRB
```

The agent will return a structured JSON result like:
```json
{
  "is_grb": true,
  "grb_name": "970828",
  "has_redshift": true,
  "z": 0.958,
  "z_err": null,
  "confidence": 0.95,
  "notes": "GRB 970828 identified in subject. Spectroscopic redshift z=0.958 reported in body."
}
```

### Analyze a specific circular for GRB content using regex
```text
> check circular at index 10 for GRB using regex
```

Result:
```json
{
  "is_grb": true,
  "match": "970828",
  "subject": "GRB 970828: ..."
}
```

### Search indexed circulars by keyword
```text
> Search for optical counterpart reports
```

### Search indexed circulars by keyword and event
```text
> Search for optical counterpart reports for EP260119a
```

### Retrieve all circulars for a specific event
```text
> Show me all circulars for GRB 260120B
```

### Retrieve one circular by circular ID
```text
> Open circular 43483
```

---

## Tools

| Tool | Description |
|------|-------------|
| `fetch_gcn_circulars` | Browse and preview raw circular JSON files by index range |
| `search_gcn_circulars` | Search indexed circulars by keyword, optionally filtered by event |
| `get_event_circulars` | Retrieve indexed circulars associated with a specific event |
| `get_gcn_circular` | Retrieve a single indexed circular by circular ID |
| `fetch_and_check_circular_for_grb` | Fetch a raw circular by index and analyze it for GRB content and redshift data using Ollama |
| `check_for_grb_regex` | Fetch a raw circular by index and use regex on its subject to check whether it is about a GRB |

---

## Internal Modules

### `utils.py`
Helper functions for:
- cleaning raw text
- normalizing event names
- extracting event IDs with regex
- extracting events from user queries

### `db.py`
Database setup logic for:
- opening SQLite connections
- enabling pragmas
- creating tables, indexes, and FTS5 virtual tables

### `indexer.py`
Ingestion logic for:
- hashing records
- inserting/updating circulars
- updating event associations
- updating FTS rows
- reading from JSON, JSONL, or directories

### `search.py`
Search logic for:
- keyword search
- event-only search
- keyword + event search
- retrieving a single circular by ID

### `tools.py`
MCP wrappers that expose the retrieval and raw-file functionality to the CLI agent.

---

## Running Tests

This project now includes unit tests for the core indexing and retrieval pipeline.

Run all tests with:

```bash
python -m pytest .\tests
```

Or run specific test files:

```bash
python -m pytest .\tests\test_utils.py
python -m pytest .\tests\test_db.py
python -m pytest .\tests\test_indexer.py
python -m pytest .\tests\test_search.py
python -m pytest .\tests\test_tools.py
```

These tests cover:

- event normalization and regex extraction
- schema creation and database setup
- ingestion/upsert behavior
- full-text search and event retrieval
- MCP tool wrappers and legacy/raw tools

---

## Notes

- The agent uses `mistral` via Ollama by default for the GRB/redshift analysis tool. This can be changed in `tools.py`.
- All analysis and indexing are done locally.
- Indexed search does **not** require Ollama; only the GRB-analysis tool does.
- If `gcn.sqlite` does not exist, it must be created by running the indexer first.
- Relative paths matter: this project assumes raw circulars are stored in the top-level `data/` directory and the SQLite index is stored as `gcn.sqlite` in the project root.

---

## Future Improvements

Possible next steps for the project include:

- adding LLM fallback for event extraction when regex fails
- adding event summarization tools
- storing human-readable timestamps in tool output
- improving redshift-focused search workflows
- packaging `src` as a formal Python package