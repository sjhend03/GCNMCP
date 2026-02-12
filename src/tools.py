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
