"""Store: per-scope mem0.Memory wrapper. Verifies isolation and merge semantics."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from mem0_memory.paths import profile_memory_dir, shared_memory_dir
from mem0_memory.store import ExtractorError, Store


def test_profile_store_uses_profile_dir(hermes_home, fake_memory_factory):
    s = Store(profile="seb", memory_factory=fake_memory_factory)
    assert s.dir == profile_memory_dir("seb")
    assert s.dir.is_dir()
    assert oct(s.dir.stat().st_mode)[-3:] == "700"
    assert s.scope_name == "profile"
    assert s.scope_kwargs == {"agent_id": "seb"}


def test_shared_store_uses_shared_dir(hermes_home, fake_memory_factory):
    s = Store(shared=True, memory_factory=fake_memory_factory)
    assert s.dir == shared_memory_dir()
    assert s.scope_name == "shared"
    # mem0 v2 OSS does not expose app_id; the shared pool is keyed by a virtual agent
    assert s.scope_kwargs == {"agent_id": "hermes-shared"}


def test_config_chroma_path_under_dir(hermes_home, fake_memory_factory):
    s = Store(profile="seb", memory_factory=fake_memory_factory)
    cfg = s.config()
    assert cfg["vector_store"]["provider"] == "chroma"
    assert cfg["vector_store"]["config"]["path"] == str(s.dir / "chroma")


def test_add_passes_scope_kwargs_to_mem0(hermes_home, fake_memory_factory):
    s = Store(profile="seb", memory_factory=fake_memory_factory)
    s.add("hello")
    fake = fake_memory_factory.instances[-1]
    assert fake.added[0]["agent_id"] == "seb"


def test_shared_add_uses_virtual_agent_id(hermes_home, fake_memory_factory):
    s = Store(shared=True, memory_factory=fake_memory_factory)
    s.add("global")
    fake = fake_memory_factory.instances[-1]
    assert fake.added[0]["agent_id"] == "hermes-shared"


def test_add_passes_user_id_and_meta(hermes_home, fake_memory_factory):
    s = Store(profile="seb", memory_factory=fake_memory_factory)
    s.add("hello", user_id="u@example.com", meta={"k": "v"})
    fake = fake_memory_factory.instances[-1]
    assert fake.added[0]["user_id"] == "u@example.com"
    assert fake.added[0]["metadata"] == {"k": "v"}


def test_search_filters_by_scope(hermes_home, fake_memory_factory):
    seb = Store(profile="seb", memory_factory=fake_memory_factory)
    assistant = Store(profile="assistant", memory_factory=fake_memory_factory)
    shared = Store(shared=True, memory_factory=fake_memory_factory)

    seb.add("seb fact")
    assistant.add("assistant fact")
    shared.add("shared fact")

    seb_results = seb.search("fact")
    seb_texts = [r["text"] for r in seb_results]
    assert "seb fact" in seb_texts
    assert "assistant fact" not in seb_texts
    assert "shared fact" not in seb_texts  # shared is read separately by CLI, not by Store

    shared_results = shared.search("fact")
    assert "shared fact" in [r["text"] for r in shared_results]


def test_sqlite_file_created_with_wal(hermes_home, fake_memory_factory):
    s = Store(profile="seb", memory_factory=fake_memory_factory)
    sqlite_path = s.dir / "store.sqlite"
    assert sqlite_path.exists()
    con = sqlite3.connect(sqlite_path)
    mode = con.execute("PRAGMA journal_mode").fetchone()[0]
    con.close()
    assert mode.lower() == "wal"


def test_raw_facts_table_present(hermes_home, fake_memory_factory):
    s = Store(profile="seb", memory_factory=fake_memory_factory)
    con = sqlite3.connect(s.dir / "store.sqlite")
    rows = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='raw_facts'"
    ).fetchall()
    con.close()
    assert rows == [("raw_facts",)]
