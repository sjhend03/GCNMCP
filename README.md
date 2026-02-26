# GCNMCP

An MCP (Model Context Protocol) agent for processing GCN (General Coordinates Network) circulars and extracting Gamma-Ray Burst (GRB) data using a local LLM.

---

## Overview

GCNMCP is a CLI-based AI agent that connects to a local MCP server to fetch and analyze GCN circulars. It uses a local Mistral model via Ollama to determine whether a circular reports a GRB event and extract relevant data such as redshift measurements.

---

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com/) with the `mistral` model pulled
- GCN circular JSON files in a `./data` directory

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
```
GCNMCP/
└── data/
    ├── 00001.json
    ├── 00002.json
    └── ...
```

Each circular JSON file should follow the GCN circular format with at minimum `subject` and `body` fields.

---

## Usage

**Start the MCP server**
```bash
python src/server.py
```

**Start the CLI agent**
```bash
python src/cli.py
```

**Example interactions**

Fetch and preview circulars by index range:
```
> fetch circulars 0 to 5
```

Analyze a specific circular for GRB content:
```
> check circular at index 10 for GRB
```

The agent will return a structured JSON result:
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

Analyze a specific circular for GRB content using regex:
```
> check circular at index 10 for GRB using regex
```

The agent will return true or false as a result:
```json
True/False
```

---

## Tools

| Tool | Description |
|------|-------------|
| `fetch_gcn_circulars` | Browse and preview circulars by index range |
| `fetch_and_check_circular_for_grb` | Fetch a circular by index and analyze it for GRB content and redshift data |
| `check_for_grb_regex` | Fetch a circular by index and use regex on it's subject to see if it's about a GRB |

---

## Notes

- The agent uses `mistral` via Ollama by default. This can be changed in `tools.py` by updating the `model_name` variable.
- All analysis is done locally — no data is sent to external APIs.