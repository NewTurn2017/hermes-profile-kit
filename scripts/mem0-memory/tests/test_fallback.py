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
