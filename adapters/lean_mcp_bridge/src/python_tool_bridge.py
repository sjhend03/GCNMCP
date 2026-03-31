#!/usr/bin/env python3
"""Local subprocess bridge for LeanMCP -> Python tool execution."""

from __future__ import annotations

import asyncio
import json
import sys
import types
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _normalize_result(result: list[object]) -> list[object]:
    normalized: list[object] = []
    for item in result:
        if hasattr(item, "text"):
            normalized.append({"type": "text", "text": getattr(item, "text")})
        else:
            normalized.append(item)
    return normalized


def _ensure_ollama_stub_if_missing() -> None:
    """Allow importing src/tools.py even if ollama package is unavailable."""
    try:
        import ollama  # type: ignore  # noqa: F401
    except Exception:
        stub = types.SimpleNamespace(
            chat=lambda *args, **kwargs: (_ for _ in ()).throw(
                RuntimeError("ollama package is not installed; required for fetch_and_check_circular_for_grb")
            )
        )
        sys.modules["ollama"] = stub


async def _main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        print(json.dumps({"error": "No JSON payload provided on stdin"}))
        return 1

    try:
        payload = json.loads(raw)
    except Exception as exc:
        print(json.dumps({"error": f"Invalid JSON payload: {exc}"}))
        return 1

    tool_name = payload.get("name")
    arguments = payload.get("arguments", {}) or {}

    if not tool_name:
        print(json.dumps({"error": "Missing required field: name"}))
        return 1

    repo_root = _repo_root()
    src_dir = repo_root / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    try:
        _ensure_ollama_stub_if_missing()
        from tools import call_tool  # type: ignore

        result = await call_tool(str(tool_name), dict(arguments))
        print(json.dumps({"result": _normalize_result(result)}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"error": f"Python bridge error: {exc}"}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
