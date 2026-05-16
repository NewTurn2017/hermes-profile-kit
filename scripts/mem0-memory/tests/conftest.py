"""Shared pytest fixtures for the mem0-memory plugin."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def hermes_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect ~/.hermes to a tmpdir for the test."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    return tmp_path / "hermes"


class FakeMemory:
    """In-memory stand-in for mem0.Memory used by Store unit tests.

    Mirrors the real mem0 v2 API: add() takes scope IDs as top-level kwargs;
    search()/get_all() take top_k=int and filters=dict.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.added: list[dict[str, Any]] = []
        self.next_id = 0

    def add(self, messages: str, **kwargs: Any) -> dict[str, Any]:
        self.next_id += 1
        rec = {"id": f"mem_{self.next_id}", "messages": messages, **kwargs}
        self.added.append(rec)
        return {"results": [{"id": rec["id"], "memory": messages, "event": "ADD"}]}

    def search(self, query: str, *, top_k: int = 20, filters: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        scope_keys = {"user_id", "agent_id", "run_id"}
        scope = {k: v for k, v in (filters or {}).items() if k in scope_keys}
        results: list[dict[str, Any]] = []
        for rec in self.added:
            if all(rec.get(k) == v for k, v in scope.items()):
                results.append({"id": rec["id"], "memory": rec["messages"], "score": 0.9})
        return {"results": results[:top_k]}

    def get_all(self, *, top_k: int = 1000, filters: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        return self.search("", top_k=top_k, filters=filters)


@pytest.fixture
def fake_memory_factory():
    """Returns a callable that builds a FakeMemory from a config dict.

    The same FakeMemory instance is returned for the same collection_name so
    that data added in one CLI invocation is visible to subsequent query/list
    invocations within the same test.
    """
    instances: list[FakeMemory] = []
    _cache: dict[str, FakeMemory] = {}

    def factory(config: dict[str, Any]) -> FakeMemory:
        key = (config.get("vector_store") or {}).get("config", {}).get("collection_name", "")
        if key and key in _cache:
            return _cache[key]
        m = FakeMemory(config)
        instances.append(m)
        if key:
            _cache[key] = m
        return m

    factory.instances = instances  # type: ignore[attr-defined]
    return factory


class SilentlyFailingMemory(FakeMemory):
    """Mimics mem0 v2 behavior when LLM extraction fails: returns empty results,
    does NOT raise."""

    def add(self, messages: str, **kwargs: Any) -> dict[str, Any]:
        return {"results": []}


@pytest.fixture
def silent_fail_memory_factory():
    instances: list[SilentlyFailingMemory] = []

    def factory(config: dict[str, Any]) -> SilentlyFailingMemory:
        m = SilentlyFailingMemory(config)
        instances.append(m)
        return m

    factory.instances = instances  # type: ignore[attr-defined]
    return factory
