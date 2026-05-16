"""Shared pytest fixtures for the mem0-memory plugin."""
from __future__ import annotations

import os
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

    Records add() calls, returns deterministic search() results filtered by scope kwargs.
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

    def search(self, query: str, *, limit: int = 5, **kwargs: Any) -> dict[str, Any]:
        scope_keys = {"user_id", "agent_id", "app_id", "run_id"}
        scope = {k: v for k, v in kwargs.items() if k in scope_keys}
        results: list[dict[str, Any]] = []
        for rec in self.added:
            if all(rec.get(k) == v for k, v in scope.items()):
                results.append({"id": rec["id"], "memory": rec["messages"], "score": 0.9})
        return {"results": results[:limit]}

    def get_all(self, **kwargs: Any) -> dict[str, Any]:
        return self.search("", limit=1000, **kwargs)


@pytest.fixture
def fake_memory_factory():
    """Returns a callable that builds a FakeMemory from a config dict."""
    instances: list[FakeMemory] = []

    def factory(config: dict[str, Any]) -> FakeMemory:
        m = FakeMemory(config)
        instances.append(m)
        return m

    factory.instances = instances  # type: ignore[attr-defined]
    return factory
