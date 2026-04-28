"""
conftest.py — shared pytest configuration for GCNMCP tests

Two problems solved here:
1. src/search.py and src/tools.py use bare imports (`from db import ...`,
   `from search import ...`) because they run with src/ on sys.path in
   production (py_bridge.py inserts it). Tests that import them as
   `src.search` would fail because the bare sibling imports then break.
   Fix: insert src/ into sys.path before collection so bare imports resolve.

2. tools.py imports `ollama` at module level. We stub it out before
   collection so tests that don't need Ollama don't require it installed.
"""

import sys
import types
from pathlib import Path

# ── 1. Make bare sibling imports inside src/ resolve ────────────────────────
_src_dir = str(Path(__file__).resolve().parent.parent / "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

# ── 2. Stub ollama so tools.py imports cleanly without the package ───────────
if "ollama" not in sys.modules:
    _ollama_stub = types.ModuleType("ollama")
    # Default stub raises — individual tests that need Ollama monkeypatch this.
    def _ollama_chat_not_installed(*args, **kwargs):
        raise RuntimeError(
            "ollama is not installed. Monkeypatch ollama.chat in your test."
        )
    _ollama_stub.chat = _ollama_chat_not_installed  # type: ignore[attr-defined]
    sys.modules["ollama"] = _ollama_stub
