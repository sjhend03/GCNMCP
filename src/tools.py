from Tool import Tool
from TextContext import TextContext

from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timezone
import json
import re
import ollama

from search import search_circulars


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = str(PROJECT_ROOT / "gcn.sqlite")
DEFAULT_DATA_DIR = str(PROJECT_ROOT / "data")


def format_timestamp(ms: int | None) -> str:
    if not ms:
        return "Unknown"
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def format_search_results(results: list[dict], empty_message: str = "No matching circulars found.") -> list[TextContext]:
    if not results:
        return [TextContext(text=empty_message)]

    contexts = []
    for r in results:
        contexts.append(
            TextContext(
                text=(
                    f"Circular ID: {r['circular_id']}\n"
                    f"Primary event: {r['primary_event']}\n"
                    f"Subject: {r['subject']}\n"
                    f"Created on: {format_timestamp(r['created_on'])}\n"
                    f"Score: {r['score']}\n"
                    f"Snippet: {r['snippet'] or ''}"
                )
            )
        )
    return contexts


async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="fetch_gcn_circulars",
            description=(
                "Load raw GCN circular JSON files by local file index range. "
                "Use this only when the user explicitly asks for raw circular files, raw JSON, "
                "or a specific file index range. "
                "This returns the raw contents of the files from start_index up to but not including end_index. "
                "Do not use this for keyword search."
            ),
            input_schema={
                "properties": {
                    "data_dir": {
                        "type": "string",
                        "description": "Local directory containing circular JSON files"
                    },
                    "start_index": {
                        "type": "integer",
                        "description": "Start file index (0-based, inclusive)"
                    },
                    "end_index": {
                        "type": "integer",
                        "description": "End file index (exclusive)"
                    }
                },
                "required": ["start_index", "end_index"]
            }
        ),

        Tool(
            name="search_gcn_circulars",
            description=(
                "Search indexed GCN circulars by keyword in the subject and body text. "
                "Use this for general searches such as 'redshift', 'GRB', 'afterglow', or 'optical counterpart'. "
                "If the user asks for a specific number of results, always set the limit field to that number. "
                "The event field is optional and should only be used for an exact specific event name such as "
                "'GRB 260120B' or 'EP260119a'. "
                "Do not use broad values like 'GRB' in the event field."
            ),
            input_schema={
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keyword query to search in indexed subject/body text, e.g. 'redshift' or 'optical counterpart'"
                    },
                    "event": {
                        "type": "string",
                        "description": "Optional exact event name only, e.g. 'GRB 260120B' or 'EP260119a'"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return; set this when the user asks for a specific number"
                    },
                }
            }
        ),

        Tool(
            name="fetch_and_check_circular_for_grb",
            description=(
                "Load one raw circular by local file index and use an LLM to decide whether it is about a GRB "
                "and whether it reports a redshift. "
                "Use this only when the user explicitly asks to analyze one specific raw circular file."
            ),
            input_schema={
                "properties": {
                    "index": {
                        "type": "integer",
                        "description": "File index of the raw circular JSON file to load"
                    },
                    "model": {
                        "type": "string",
                        "description": "Ollama model name to use for analysis, e.g. 'mistral' or 'llama3.1:8b'"
                    },
                    "data_dir": {
                        "type": "string",
                        "description": "Directory containing circular JSON files"
                    }
                },
                "required": ["index"]
            }
        ),

        Tool(
            name="check_for_grb_regex",
            description=(
                "Load one raw circular by local file index and check whether its subject line contains a GRB designation using regex. "
                "Use this only for a fast regex check on one specific raw circular file."
            ),
            input_schema={
                "properties": {
                    "index": {
                        "type": "integer",
                        "description": "File index of the raw circular JSON file to load"
                    },
                    "data_dir": {
                        "type": "string",
                        "description": "Directory containing circular JSON files"
                    }
                },
                "required": ["index"]
            }
        )
    ]


async def call_tool(name: str, arguments: Dict[str, Any]) -> List[Any]:
    if name == "ping_python":
        return [TextContext(text=json.dumps({"message": "pong from python"}, ensure_ascii=False))]
    
    if name == "fetch_gcn_circulars":
        results = load_circular_files(
            arguments.get("data_dir", DEFAULT_DATA_DIR),
            arguments.get("start_index"),
            arguments.get("end_index")
        )
        return results

    if name == "search_gcn_circulars":
        try:
            results = search_circulars(
                db_path=DEFAULT_DB_PATH,
                query=arguments.get("query", "") or "",
                event=arguments.get("event"),
                limit=int(arguments.get("limit", 10)),
            )
            return format_search_results(results)
        except Exception as e:
            return [TextContext(text=f"Error in {name}: {e}")]

    if name == "fetch_and_check_circular_for_grb":
        index = int(arguments.get("index", 0))
        data_dir = arguments.get("data_dir", DEFAULT_DATA_DIR)
        circulars = load_circular_files(data_dir, index, index + 1)

        if not circulars:
            return [TextContext(text=json.dumps({"error": "No circular found at that index"}))]

        raw_text = circulars[0].text
        try:
            content = json.loads(raw_text)
        except Exception as e:
            return [TextContext(text=f"Error parsing content: {e}")]

        model_name = arguments.get("model", "mistral")

        system_prompt = """
        You are an astrophysicist analyzing GCN circulars about astronomical observations.

        Your task:
        1. Determine if the circular is about a GRB (Gamma-Ray Burst)
        - Look for "GRB" in the subject line or body
        - Look for GRB designations like "GRB 970828", "GRB970828", etc.

        2. Determine if a redshift (z) measurement is reported
        - Look for explicit mentions: "z =", "redshift", "z~", "at z of"
        - Common phrases: "spectroscopic redshift", "photometric redshift"
        - If no redshift is mentioned, has_redshift should be False

        CRITICAL: If you see "GRB" followed by a date (like "GRB 970828"), that IS a GRB event.
        CRITICAL: When returning the grb_name DO NOT INCLUDE GRB, just the number and letter combo.

        Return ONLY valid JSON in this exact format:
        {
            "is_grb": true,
            "grb_name": "071028B",
            "has_redshift": false,
            "z": null,
            "z_err": null,
            "confidence": 0.95,
            "notes": "Brief explanation of your analysis"
        }
        """

        prompt = f"""
        Analyze this GCN circular and determine whether it is about a GRB and whether it reports a redshift:

        {json.dumps(content, ensure_ascii=False)}
        """

        res = ollama.chat(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        )

        raw = res["message"]["content"].strip()

        try:
            parsed = json.loads(raw)
            return [TextContext(text=json.dumps(parsed, ensure_ascii=False))]
        except Exception:
            pass

        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                return [TextContext(text=json.dumps(parsed, ensure_ascii=False))]
            except Exception:
                pass

        return [TextContext(text=json.dumps({
            "error": "Could not parse model output as JSON",
            "raw_output": raw
        }, ensure_ascii=False))]

    if name == "check_for_grb_regex":
        data_dir = Path(arguments.get("data_dir", DEFAULT_DATA_DIR))
        json_files = sorted(data_dir.glob("*.json"))
        index = int(arguments.get("index", 0))

        if index < 0 or index >= len(json_files):
            return [TextContext(text=json.dumps({
                "error": f"Index {index} out of range for {len(json_files)} files"
            }))]

        circular = json.loads(json_files[index].read_text(encoding="utf-8"))
        subject = circular.get("subject", "")

        match = re.search(r'GRB\s*(\d{6}\w?)', subject, re.IGNORECASE)
        return [TextContext(text=json.dumps({
            "is_grb": bool(match),
            "match": match.group(1) if match else None,
            "subject": subject
        }, ensure_ascii=False))]
    
    if name == "extract_wavelength":
        body = arguments.get("body")

        if not body:
            return [TextContext(text="No body to extract wavelength")]
        
        try:
            body = json.load(body)
        except Exception as e:
            return [TextContext(text=f"Error parsing body: {e}")]

        system_prompt = """

        """

        prompt = """

        """

        res = ollama.chat(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        )

        raw = res["message"]["content"].strip()

        return [TextContext()]

    return [TextContext(text=json.dumps({"error": f"Unknown tool: {name}"}))]


def load_circular_files(data_dir: str, start_index: int, end_index: int):
    data_dir = Path(data_dir)
    json_files = sorted(data_dir.glob("*.json"))

    if start_index is None:
        start_index = 0
    if end_index is None:
        end_index = min(start_index + 10, len(json_files))

    if end_index == start_index:
        end_index = start_index + 1

    selected = json_files[start_index:end_index]

    results = []
    for f in selected:
        try:
            content = f.read_text(encoding="utf-8")
            results.append(TextContext(text=content))
        except Exception as e:
            results.append(TextContext(text=f"Error reading {f}: {e}"))

    return results