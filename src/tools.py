from Tool import Tool
from TextContext import TextContext

import ollama
from pathlib import Path
from typing import Dict, Any, List
import json
import re

async def list_tools() -> List[Tool]:
    """
    Lists all tools with their name, descriptions, and input schema (args)
    """
    return [
        Tool(
            name="fetch_gcn_circulars",
            description="Browses and previews multiple NASA GCN circulars.",
            input_schema={
                "properties": {
                    "data_dir": {"type": "string", "description": "Local directory to load the circulars from, leave blank if not specified"},
                    "start_index": {"type": "integer", "description": "Index of the first file to fetch, 0-based. To fetch a single file at position N, set start_index=N and end_index=N+1"},
                    "end_index": {"type": "integer", "description": "Index to stop at (exclusive). To fetch a single file at position N, set start_index=N and end_index=N+1. Example: start=10, end=11 fetches one file."}
                }
            }
        ),
        Tool(
            name="fetch_and_check_circular_for_grb",
            description="Fetches a singular circular and then check it for GRB relavent GRB information.",
            input_schema={
                "properties": {
                    "index": {
                        "type": "integer",
                        "description": "Index of circular to load and check for GRB"
                    },
                    "model": {
                        "type": "string",
                        "description": "Name of the LLM on Ollama to use for prompting, leave blank if none specified"
                    }
                }
            }
        ),
        Tool(
            name="check_for_grb_regex",
            description="Checks a circulars subject for the word GRB USING REGEX and returns True of False",
            input_schema={
                "properties": {
                    "index": {
                        "type": "integer",
                        "description": "Index of circular to load and check for GRB"
                    }
                }
            }
        )
    ]

async def call_tool(name: str, arguments: Dict[str, Any]) -> List[Any]:
    """
    Runs specified tool with specified arguments.
    name: tool name
    arguements: arguments for the specified tool to use
    """
    if name == "fetch_gcn_circulars":
        """
        Fetchs gcn circulars from a local directory with a specified start index as the first 
        circular to fetch up to the end index.
        """
        results = load_circular_files(arguments.get("data_dir", "./data"), arguments.get("start_index"), arguments.get("end_index"))
        return results
        
    if name == "fetch_and_check_circular_for_grb":
        """
        Fetches a singular circular and prompts an LLM to check if the circular is about a GRB
        and if so to extract relevant information
        """
        index = arguments.get("index", 0)
        circular = load_circular_files("./data", index, index)[0]      
        
        if isinstance(circular, str): # Ensure type
            try:
                content = json.loads(circular)
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
        CRITICAL: When returning the grb_name DO NOT INCLUDE GRB just the number and letter combo

        Return ONLY valid JSON in this exact format:
        {
            "is_grb": true,
            "grb_name:" "071028B",
            "has_redshift": false,
            "z": null,
            "z_err": null,
            "confidence": 0.95,
            "notes": "Brief explanation of your analysis"
        }

        Rules:
        - Use null (not None) for missing values
        - Use lowercase true/false (not True/False)
        - confidence is between 0 and 1
        - Keep notes brief (1-2 sentences)
        """

        prompt = f"""
        Analyze this GCN circular to determine wether it is about a GRB and if so, extract the relevant data specified in the system prompt:

        {content}
        """
        res = ollama.chat(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        )

        raw = res["message"]["content"].strip()

        # Try direct parse first
        try:
            parsed = json.loads(raw)
            return [TextContext(text=json.dumps(parsed))]
        except Exception:
            pass

        # Try to extract JSON from markdown code blocks or anywhere in the response
        json_match = re.search(r'\{[^{}]*"is_grb"[^{}]*\}', raw, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                return [TextContext(text=json.dumps(parsed))]
            except Exception:
                pass

        print("RAW MODEL OUTPUT:")
        print(raw)
        return [TextContext(text=json.dumps({...}))]  # If parsing does't work dump everything

    if name == "check_for_grb_regex":
        """
        Uses regex to check if a circular is about a GRB
        """
        data_dir = Path("./data")
        json_files = sorted(data_dir.glob("*.json"))
        index = arguments.get("index", 0)
        circular = json.loads(json_files[index].read_text(encoding="utf-8"))
        subject = circular.get("subject", "")

        match = re.search(r'GRB\s*(\d{6}\w?)', subject, re.IGNORECASE)
        if match:
            return [TextContext(text="True")]
        else:
            return [TextContext(text="False")]
        
def load_circular_files(data_dir, start_index, end_index):
    """
    Helper function to load local circulars starting from start_index and ending with end_index
    start_index: first index to load 
    end_index: index to stop loading
    """
    data_dir = Path(data_dir)
    json_files = sorted(data_dir.glob("*.json"))

    # If start and end are the same, user wants a single file
    if end_index is not None and end_index == start_index:
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