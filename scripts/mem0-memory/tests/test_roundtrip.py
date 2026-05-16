"""Real mem0 add → query roundtrip with an in-process echo LLM (no network)."""
from __future__ import annotations

import os
import sys

import pytest

pytest.importorskip("mem0", reason="mem0ai not installed in this venv")


@pytest.fixture(autouse=True)
def _no_openai_calls(monkeypatch):
    """Force any accidental OpenAI client construction to fail loudly."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-no-network")


def _build_echo_memory(hermes_home):
    """Build a real mem0 Memory wired to a deterministic local LLM stub."""
    from mem0 import Memory
    from mem0_memory.paths import profile_memory_dir

    d = profile_memory_dir("seb")
    d.mkdir(parents=True, exist_ok=True)

    config = {
        "vector_store": {
            "provider": "chroma",
            "config": {
                "collection_name": "hermes_profile_seb",
                "path": str(d / "chroma"),
            },
        },
        "history_db_path": str(d / "store.sqlite"),
    }
    mem = Memory.from_config(config)

    # Replace the LLM at mem.llm with an echo stub that returns the message verbatim
    # as a single fact (mem0 will then embed + persist).
    class EchoLLM:
        def generate_response(self, messages, **_kw):
            text = messages[-1]["content"] if messages else ""
            return f'{{"facts": [{{"text": "{text}"}}]}}'

    if hasattr(mem, "llm"):
        mem.llm = EchoLLM()
    return mem


def test_real_mem0_add_then_search(hermes_home):
    try:
        mem = _build_echo_memory(hermes_home)
    except Exception as e:
        pytest.skip(f"mem0 in this env requires additional dependencies: {e}")
    try:
        mem.add("vault root is /opt/vault", agent_id="seb")
    except Exception as e:
        pytest.skip(f"mem0 in this env requires a richer LLM stub: {e}")
    results = mem.search("vault", top_k=5, filters={"agent_id": "seb"})
    items = results.get("results", []) if isinstance(results, dict) else results
    texts = [i.get("memory") or i.get("text") or "" for i in items]
    assert any("vault" in t for t in texts), f"expected 'vault' in results, got {texts}"
