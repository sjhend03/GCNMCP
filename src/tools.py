from Tool import Tool
from TextContext import TextContext

import ollama
from pathlib import Path
from typing import Dict, Any, List
import asyncio
import json

async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="fetch_gcn_circular_name_local",
            description="List local circular JSON files"
        ),
        Tool(
            name="fetch_gcn_circular_local",
            description="Load one or more circular JSON files"
        ),
        Tool(
            name="check_circular_for_grb",
            description="Use LLM to extract GRB redshift info"
        ),
    ]

async def call_tool(name: str, arguments: Dict[str, Any]) -> List[Any]:

    if name == "fetch_gcn_circular_name_local":
        data_dir = Path(arguments.get("data_dir_name", "./data"))
        json_files = sorted(data_dir.glob("*.json"))
        return [str(f) for f in json_files]
    
    if name == "load_gcn_circular":
        path = arguments.get("path")
        encoding = arguments.get("encoding", "utf-8")
        try:
            loop = asyncio.get_event_loop()
            content = await loop.run_in_executor(
                None,
                lambda: Path(path).read_text(encoding=encoding)
            )

            return [TextContext(text=content)]
        except Exception as e:
            return [TextContext(text=e)]
        
    if name == "check_for_grb_redshift":
        content = arguments.get("content")
        model_name = "mistral"
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
        Analyze this GCN circular:

        Subject: {content.get('subject', 'N/A')}

        Body:
        {content.get('body', '')}
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
            return parsed
        except Exception:
            print("RAW MODEL OUTPUT:")
            print(raw)
            return {
                "is_grb": False,
                "has_redshift": False,
                "z": None,
                "z_err": None,
                "confidence": None,
                "notes": "raw",
            }
    if name == "check_for_grb_redshift_batch":
        content = arguments.get("content")
        circular_ids = arguments.get("circular_ids", [])
        
        model_name = "mistral"
        system_prompt = """
        You are analyzing multiple GRB circulars at once. Each circular is marked with ---CIRCULAR ID---.
        
        For EACH circular, determine:
        1. Is it about a GRB?
        2. Does it contain a redshift measurement?
        
        Return a JSON object where each key is the circular ID and the value contains the analysis.
        
        Format:
        {
            "GRB_0": {
                "is_grb": true,
                "grb_name": "071028B",
                "has_redshift": true,
                "z": 2.45,
                "z_err": 0.05,
                "confidence": 0.95
            },
            "GRB_1": {
                "is_grb": true,
                "grb_name": "080210A",
                "has_redshift": false,
                "z": null,
                "z_err": null,
                "confidence": 0.90
            }
        }
        
        CRITICAL: 
        - Return ONLY valid JSON, no markdown
        - Use null for missing values
        - Use lowercase true/false
        - grb_name should NOT include "GRB", just the number/letter combo
        """
        
        prompt = f"Analyze these {len(circular_ids)} circulars:\n\n{content}"
        
        res = ollama.chat(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        )
        
        raw = res["message"]["content"].strip()
        
        # Clean up markdown code blocks
        if raw.startswith('```json'):
            raw = raw.split('```json')[1]
        if raw.startswith('```'):
            raw = raw.split('```', 1)[1]
        if raw.endswith('```'):
            raw = raw.rsplit('```', 1)[0]
        raw = raw.strip()
        
        try:
            parsed = json.loads(raw)
            return [TextContext(text=json.dumps(parsed))]
        except Exception as e:
            print("RAW BATCH MODEL OUTPUT:")
            print(raw)
            print(f"Parse error: {e}")
            return [TextContext(text=json.dumps({
                "error": str(e),
                "raw": raw
            }))]
