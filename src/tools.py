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
        You are an astrophysicist analyzing GCN circulars which are human written 
        notes on observations in the sky.
        Your task is to look at each GCN circualar and determine if the circular is 
        about a GRB (Gamma ray burst) and if the circular has a labeled redshift.

        ONLY return json in this format:
        {
                "is_grb": True/False,
                "has_redshift": True/False,
                "z": int/float,
                "z_err": int/float,
                "confidence": float (percentage out of 1),
                "notes": "(body of the text)",
        }
"""
        prompt = f"""
        analyze this circular:
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
