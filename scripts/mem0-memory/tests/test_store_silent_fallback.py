"""Silent-extraction-failure fallback: when mem0 returns no facts for non-empty input,
Store.add must persist the raw text to `raw_facts` so the original message is recoverable."""
from __future__ import annotations

import sqlite3

from mem0_memory.store import Store


def test_silent_failure_falls_back_to_raw_facts(hermes_home, silent_fail_memory_factory):
    s = Store(profile="seb", memory_factory=silent_fail_memory_factory)
    result = s.add("seb keeps the vault at /opt/vault")

    assert result["extracted"] is False
    assert result["raw_id"] is not None

    con = sqlite3.connect(s.dir / "store.sqlite")
    try:
        rows = con.execute("SELECT text FROM raw_facts").fetchall()
    finally:
        con.close()
    assert rows == [("seb keeps the vault at /opt/vault",)]


def test_silent_failure_search_finds_raw_fact(hermes_home, silent_fail_memory_factory):
    s = Store(profile="seb", memory_factory=silent_fail_memory_factory)
    s.add("vault path is /opt/vault")
    hits = s.search("vault", limit=5)
    assert any(h.get("raw") for h in hits)
    assert any("/opt/vault" in h["text"] for h in hits)


def test_successful_extraction_does_not_save_raw(hermes_home, fake_memory_factory):
    """When extraction works, no raw fallback row should be created."""
    s = Store(profile="seb", memory_factory=fake_memory_factory)
    result = s.add("seb likes filesystem isolation")

    assert result["extracted"] is True
    assert result["raw_id"] is None

    con = sqlite3.connect(s.dir / "store.sqlite")
    try:
        rows = con.execute("SELECT COUNT(*) FROM raw_facts").fetchone()
    finally:
        con.close()
    assert rows == (0,)
