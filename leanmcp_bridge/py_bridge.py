#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import sys
import types
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def normalize_result(result: list[object]) -> list[object]:
    normalized: list[object] = []

    for item in result:
        if hasattr(item, "text"):
            normalized.append({
                "type": "text",
                "text": getattr(item, "text"),
            })
        else:
            normalized.append(item)

    return normalized


def ensure_ollama_stub_if_missing() -> None:
    try:
        import ollama
    except Exception:
        stub = types.SimpleNamespace(
            chat=lambda *args, **kwargs: (_ for _ in ()).throw(
                RuntimeError(
                    "ollama package is not installed; required for Ollama-backed tools"
                )
            )
        )
        sys.modules["ollama"] = stub


async def main_async() -> int:
    raw = sys.stdin.read()

    if not raw.strip():
        print(json.dumps({"ok": False, "error": "No input provided"}))
        return 1

    try:
        payload = json.loads(raw)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"Invalid JSON payload: {exc}"}))
        return 1

    tool = payload.get("tool")
    arguments = payload.get("arguments", {}) or {}

    if not tool:
        print(json.dumps({"ok": False, "error": "Missing required field: tool"}))
        return 1

    root = repo_root()
    src_dir = root / "src"

    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    try:
        ensure_ollama_stub_if_missing()

        from tools import call_tool

        result = await call_tool(str(tool), dict(arguments))
        print(json.dumps({"ok": True, "result": normalize_result(result)}, ensure_ascii=False))
        return 0

    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main_async()))