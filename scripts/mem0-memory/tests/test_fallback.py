"""Extractor failure → raw_facts row written; query falls back to LIKE search."""
from __future__ import annotations

import json
import sqlite3

import pytest

from mem0_memory.paths import profile_memory_dir
from mem0_memory.store import ExtractorError, Store


class ExplodingMemory:
    """Memory factory that always raises on add() (simulates LLM extractor failure).

    Mirrors mem0 v2 API: add() takes scope kwargs; search()/get_all() take top_k+filters.
    """
    def __init__(self, config):
        self.config = config

    def add(self, messages, **_kw):
        raise RuntimeError("openai key missing")

    def search(self, query, *, top_k=20, filters=None, **_kw):
        return {"results": []}

    def get_all(self, *, top_k=20, filters=None, **_kw):
        return {"results": []}


@pytest.fixture
def exploding_factory():
    return lambda cfg: ExplodingMemory(cfg)


def test_add_failure_saves_raw(hermes_home, exploding_factory):
    s = Store(profile="seb", memory_factory=exploding_factory)
    with pytest.raises(ExtractorError):
        s.add("important fact")

    con = sqlite3.connect(profile_memory_dir("seb") / "store.sqlite")
    rows = con.execute("SELECT text FROM raw_facts").fetchall()
    con.close()
    assert ("important fact",) in rows


def test_search_falls_back_to_raw_facts(hermes_home, exploding_factory):
    s = Store(profile="seb", memory_factory=exploding_factory)
    with pytest.raises(ExtractorError):
        s.add("vault is at /opt/vault")

    results = s.search("vault", limit=5)
    texts = [r["text"] for r in results]
    assert "vault is at /opt/vault" in texts
    assert all(r["raw"] is True for r in results if r["text"] == "vault is at /opt/vault")


class HighVolumeMemory:
    """Memory factory that returns `limit` mem0 results regardless of query."""
    def __init__(self, config):
        self.config = config

    def add(self, messages, **_kw):
        # No-op: pretend extraction succeeded for high-volume scenarios.
        return {"results": [{"id": "ok", "memory": messages, "event": "ADD"}]}

    def search(self, query, *, top_k=20, filters=None, **_kw):
        # Return top_k generic chaff items — none of which are the raw fact under test.
        results = [
            {"id": f"chaff_{i}", "memory": f"unrelated chaff {i}", "score": 0.5}
            for i in range(top_k)
        ]
        return {"results": results}

    def get_all(self, *, top_k=20, filters=None, **_kw):
        return self.search("", top_k=top_k, filters=filters)


@pytest.fixture
def high_volume_factory():
    return lambda cfg: HighVolumeMemory(cfg)


def test_raw_item_reserved_when_mem0_fills_limit(hermes_home, high_volume_factory):
    """When mem0 returns `limit` items and raw_facts has a match, raw still surfaces."""
    s = Store(profile="seb", memory_factory=high_volume_factory)
    # Manually inject a raw row (simulates a past extractor failure)
    s._save_raw("the important raw fact about vault", None)

    results = s.search("vault", limit=5)
    texts = [r["text"] for r in results]
    assert len(results) == 5
    assert "the important raw fact about vault" in texts
    # 4 of the 5 are mem0 chaff, the last is raw
    assert sum(1 for r in results if r["raw"]) == 1


def test_search_item_shape_includes_ts_and_app_id(hermes_home, fake_memory_factory):
    """All returned items must have the documented shape: ts and app_id keys present."""
    s = Store(profile="seb", memory_factory=fake_memory_factory)
    s.add("fact one")
    results = s.search("fact", limit=5)
    assert results, "expected at least one result"
    for r in results:
        assert "ts" in r
        assert "app_id" in r
        assert "agent_id" in r
        assert "scope" in r
        assert "raw" in r
