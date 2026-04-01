#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

def ping_python():
    return {"message": "pong from python"}

def check_for_grb_regex(index: int, data_dir: str = "./data"):
    print(json.dumps({
        "cwd": str(Path.cwd()),
        "resolved_data_dir": str(Path(data_dir).resolve())
    }), file=sys.stderr)
    data_path = Path(data_dir)
    json_files = sorted(data_path.glob("*.json"))

    if index < 0 or index >= len(json_files):
        return {
            "is_grb": False,
            "match": None,
            "error": f"Index {index} is out of range. There are only {len(json_files)} JSON files."
        }
    
    circular = json.loads(json_files[index].read_text(encoding="utf-8"))
    subject = circular.get("subject", "")

    match = re.search(r"GRB\s*(\d{6}[A-Za-z]?)", subject, re.IGNORECASE)

    return {
        "is_grb": bool(match),
        "match": match.group(1) if match else None,
        "subject": subject,
        "file": json_files[index].name
    }

def dispatch(tool: str, arguments: dict):
    if tool == "ping_python":
        return ping_python()
    
    if tool == "check_for_grb_regex":
        return check_for_grb_regex(
            index=int(arguments.get("index", 0)),
            data_dir=arguments.get("data_dir", "./data")
        )
    
    raise ValueError(f"Unknown tool: {tool}")

def main():
    raw = sys.stdin.read()

    if not raw.strip():
        print(json.dumps({"ok": False, "error": "No input provided"}))
        raise SystemExit(1)
    
    try:
        payload = json.loads(raw)
        tool = payload["tool"]
        arguments = payload.get("arguments", {}) or {}
        result = dispatch(tool, arguments)
        print(json.dumps({"ok": True, "result": result}))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        raise SystemExit(1)
    

if __name__ == "__main__":
    main()
