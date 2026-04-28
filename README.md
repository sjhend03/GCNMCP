# GCNMCP

An MCP server for searching and analyzing [GCN (General Coordinates Network)](https://gcn.nasa.gov/) circulars — NASA's alert network for high-energy astrophysical events like gamma-ray bursts (GRBs). It exposes tools to fetch, index, and search circulars through a TypeScript [LeanMCP](https://www.leanmcp.com) HTTP server that delegates to a Python backend.

---

## Architecture

```
  MCP Client
       │
       ▼  HTTP (Streamable HTTP Transport)
┌─────────────────────────────────────┐
│  leanmcp_bridge/                    │  TypeScript / LeanMCP
│  ├── main.ts                        │  HTTP server (port 3001)
│  ├── mcp/gcn/index.ts               │  @Tool definitions & input schemas
│  └── bridge/                        │
│       ├── python_bridge.ts          │  Spawns py_bridge.py, JSON IPC
│       ├── bridge_types.ts           │  Request / response types
│       └── bridge_errors.ts          │  Typed error classes
└────────────┬────────────────────────┘
             │  stdin / stdout (JSON)
             ▼
┌─────────────────────────────────────┐
│  leanmcp_bridge/py_bridge.py        │  Python subprocess entry point
└────────────┬────────────────────────┘
             │  imports
             ▼
┌─────────────────────────────────────┐
│  src/                               │  Python core logic
│  ├── tools.py                       │  Tool dispatcher (call_tool)
│  ├── search.py                      │  SQLite FTS5 search & ranking
│  ├── indexer.py                     │  JSON ingestion + upsert pipeline
│  ├── db.py                          │  SQLite schema & connection
│  └── utils.py                       │  Event normalization & regex
└────────────┬────────────────────────┘
             │
             ▼
      gcn.sqlite   +   data/
```

Each tool call received by the TypeScript server is forwarded to the Python backend via a subprocess. `py_bridge.py` reads JSON from stdin, routes to `src/tools.py`, and returns results as JSON on stdout.

---

## Requirements

- **Node.js** 18+ and npm
- **Python** 3.10+
- SQLite with FTS5 support (included in standard Python builds)
- [Ollama](https://ollama.com/) with `mistral` pulled — only needed for the LLM classification tool

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/sjhend03/GCNMCP.git
cd GCNMCP
```

### 2. Install TypeScript dependencies

```bash
cd leanmcp_bridge
npm install
cd ..
```

### 3. Install Python dependencies

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install requests ollama pytest
pip install -r requirements.txt
```

### 4. Download GCN circulars

Create the `data/` directory and run the included fetch script to download all available circulars from the GCN API:

```bash
mkdir data
python src/fetch_circulars.py
```

Or place your own circular JSON files in `data/` manually. Each file should follow the standard GCN format:

```json
{
  "circularId": 43493,
  "subject": "GRB 260120B: Swift-BAT refined analysis",
  "eventId": "GRB 260120B",
  "createdOn": 1769036892952,
  "submitter": "D. R. Sadaula at NASA GSFC <dev.r.sadaula@nasa.gov>",
  "format": "text/plain",
  "body": "Using the data set from T-769 to T+303 sec..."
}
```

### 5. Build the SQLite search index

```bash
python -c "import sys; sys.path.append('src'); from indexer import ingest_path; ingest_path('gcn.sqlite', 'data')"
```

This reads all JSON files from `data/` and populates `gcn.sqlite`. Re-running after adding new circulars is safe — already-indexed records are skipped via content hashing.

---

## Running the Server

```bash
cd leanmcp_bridge
npm run dev
```

```
Server is running on port 3001
MCP endpoint: http://localhost:3001/mcp
Health check: http://localhost:3001/health
```

Visit `http://localhost:3001/mcp` in a browser to use LeanMCP's built-in interface for testing tools interactively.

---

## Tools

### `ping`
TypeScript health check.
- **Returns:** `"pong from typescript"`

### `ping_python`
End-to-end bridge health check — round-trips through the subprocess bridge to Python.
- **Returns:** `"pong from python"`

### `fetch_gcn_circulars`
Load raw GCN circular JSON files from local storage by index range.
- **Inputs:** `start_index` (int), `end_index` (int), `data_dir?` (string, default `"data"`)
- **Returns:** Raw circular JSON for each file in range

### `search_gcn_circulars`
Full-text search over all indexed circulars using SQLite FTS5.
- **Inputs:** `query` (string), `event?` (string, e.g. `"GRB260120B"`), `limit?` (1–100, default 10)
- **Returns:** Matching circulars with ranked snippets. Exact event matches are ranked above general text matches.

### `fetch_and_check_circular_for_grb`
Fetch a raw circular and use a local Ollama LLM to classify whether it reports a GRB and whether a redshift measurement is present.
- **Inputs:** `index` (int), `model?` (string, default `"mistral"`), `data_dir?` (string)
- **Returns:** `{ is_grb, grb_name, has_redshift, z, confidence, notes }`
- **Requires:** Ollama running locally with the specified model pulled

### `check_for_grb_regex`
Fast regex check of a circular's subject line for a GRB designation — no LLM required.
- **Inputs:** `index` (int), `data_dir?` (string)
- **Returns:** `{ is_grb, match, subject }`

---

## Project Structure

```
GCNMCP/
├── data/                            # Raw GCN circular JSON files (not committed)
├── gcn.sqlite                       # Local SQLite search index (not committed)
│
├── leanmcp_bridge/                  # TypeScript LeanMCP HTTP server
│   ├── main.ts                      # Server entry point
│   ├── package.json                 # npm dependencies
│   ├── tsconfig.json                # TypeScript compiler config
│   ├── py_bridge.py                 # Python bridge entry point (runs as subprocess)
│   ├── mcp/gcn/
│   │   ├── index.ts                 # GcnService: all @Tool definitions
│   │   └── input_schema.ts          # Input schema classes with @SchemaConstraint
│   └── bridge/
│       ├── python_bridge.ts         # callPythonTool(): JSON IPC over stdin/stdout
│       ├── bridge_types.ts          # PythonBridgeRequest / PythonBridgeResponse types
│       └── bridge_errors.ts         # PythonBridgeError, LaunchError, ParseError
│
├── src/                             # Python backend
│   ├── tools.py                     # call_tool() dispatcher
│   ├── search.py                    # FTS5 search with ranked results
│   ├── indexer.py                   # Ingestion pipeline: hash, upsert, FTS update
│   ├── db.py                        # SQLite schema creation and connection management
│   ├── fetch_circulars.py           # Standalone script to download from gcn.nasa.gov
│   ├── utils.py                     # Event normalization and regex extraction
│   ├── TextContext.py               # Response wrapper: {type: "text", text: ...}
│   └── Tool.py                      # Tool metadata wrapper
│
└── tests/                           # Python unit tests (pytest)
    ├── conftest.py                  # sys.path setup, Ollama stub
    ├── test_db.py                   # Schema creation and connection tests
    ├── test_indexer.py              # Ingestion and upsert behavior
    ├── test_search.py               # FTS keyword and event retrieval
    ├── test_tools.py                # Tool dispatcher and output format
    ├── test_utils.py                # Event normalization and regex patterns
    └── test_py_bridge.py            # Subprocess bridge integration tests
```

---

## Running Tests

```bash
python -m pytest tests/
```

Run a specific file:

```bash
python -m pytest tests/test_search.py
```

Tests stub out Ollama via `conftest.py`, so no local LLM installation is required for the test suite.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `3001` | Port the LeanMCP HTTP server listens on |
| `GCN_PYTHON_BIN` | `python` | Python interpreter used to invoke `py_bridge.py` |
| `GCN_PYTHON_BRIDGE_SCRIPT` | auto-resolved | Path to `py_bridge.py` (override for non-standard layouts) |

---

## Troubleshooting

**`gcn.sqlite` not found** — Run the indexer step (Setup step 5) before starting the server or using any search tools.

**`ollama` import error** — Install Ollama (`pip install ollama`) and ensure the Ollama daemon is running locally. The LLM tool (`fetch_and_check_circular_for_grb`) requires it; all other tools work without it.

**`data/` directory is empty** — Run `python src/fetch_circulars.py` to download circulars from the GCN API, or populate `data/` manually.

**Port 3001 already in use** — Set a different port with `PORT=<n> npm run dev`.

---

## Notes

- All indexing and search runs locally — no external API calls except for `fetch_circulars.py` and the Ollama tool.
- The Ollama tool uses `mistral` by default; pass a `model` argument to use a different locally-pulled model.
- Each tool call spawns a new Python subprocess. This keeps the bridge simple and stateless at a small per-call startup cost.
