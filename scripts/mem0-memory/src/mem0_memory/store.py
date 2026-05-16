"""Per-scope mem0.Memory wrapper + raw_facts fallback table.

mem0 v2 API contract: Memory.add takes scope IDs as top-level kwargs (user_id,
agent_id, run_id; no app_id). Memory.search and Memory.get_all take top_k= and
filters=dict. The "shared" pool is therefore keyed by a virtual agent_id
("hermes-shared"), and filesystem isolation (separate directory) is the
primary safety boundary.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Callable

from mem0_memory.paths import profile_memory_dir, shared_memory_dir


class ExtractorError(RuntimeError):
    """Raised when mem0's LLM-based fact extractor fails."""


MemoryFactory = Callable[[dict[str, Any]], Any]


def _default_factory(config: dict[str, Any]) -> Any:
    from mem0 import Memory  # local import keeps import cheap until needed
    return Memory.from_config(config)


class Store:
    def __init__(
        self,
        *,
        profile: str | None = None,
        shared: bool = False,
        memory_factory: MemoryFactory | None = None,
    ) -> None:
        if shared:
            self.scope_name = "shared"
            self.dir = shared_memory_dir()
            # mem0 OSS has no app_id; the shared pool is a virtual agent.
            # Filesystem isolation (separate dir) is the primary safety boundary.
            self.scope_kwargs: dict[str, str] = {"agent_id": "hermes-shared"}
        else:
            if profile is None:
                raise ValueError("Store requires either profile=<name> or shared=True")
            self.scope_name = "profile"
            self.dir = profile_memory_dir(profile)
            self.scope_kwargs = {"agent_id": profile}

        self.dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.dir.chmod(0o700)

        self._factory: MemoryFactory = memory_factory or _default_factory
        self._mem: Any = None
        self._init_sqlite()

    def _init_sqlite(self) -> None:
        con = sqlite3.connect(self.dir / "store.sqlite")
        try:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute(
                "CREATE TABLE IF NOT EXISTS raw_facts("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "text TEXT NOT NULL,"
                "meta TEXT,"
                "ts TEXT DEFAULT (datetime('now'))"
                ")"
            )
            con.commit()
        finally:
            con.close()

    def config(self) -> dict[str, Any]:
        return {
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "collection_name": f"hermes_{self.scope_name}",
                    "path": str(self.dir / "chroma"),
                },
            },
            "history_db_path": str(self.dir / "store.sqlite"),
        }

    @property
    def mem(self) -> Any:
        if self._mem is None:
            self._mem = self._factory(self.config())
        return self._mem

    def add(self, text: str, *, user_id: str | None = None, meta: dict[str, Any] | None = None) -> dict[str, Any]:
        # mem0 v2 Memory.add takes scope IDs as top-level kwargs.
        kwargs: dict[str, Any] = dict(self.scope_kwargs)
        if user_id:
            kwargs["user_id"] = user_id
        if meta:
            kwargs["metadata"] = meta
        try:
            result = self.mem.add(text, **kwargs)
        except Exception as exc:
            self._save_raw(text, meta)
            raise ExtractorError(str(exc)) from exc
        return {"raw_result": result, "scope": self.scope_name}

    def _save_raw(self, text: str, meta: dict[str, Any] | None) -> int:
        import json
        con = sqlite3.connect(self.dir / "store.sqlite")
        try:
            cur = con.execute(
                "INSERT INTO raw_facts(text, meta) VALUES (?, ?)",
                (text, json.dumps(meta) if meta else None),
            )
            con.commit()
            return cur.lastrowid or 0
        finally:
            con.close()

    def search(self, q: str, *, limit: int = 5) -> list[dict[str, Any]]:
        # mem0 v2 Memory.search uses top_k= and filters= (scope IDs go inside filters).
        raw_result = self.mem.search(q, top_k=limit, filters=self.scope_kwargs)
        items = raw_result.get("results", []) if isinstance(raw_result, dict) else raw_result
        return [
            {
                "id": item.get("id"),
                "text": item.get("memory") or item.get("text") or "",
                "score": float(item.get("score", 0.0)),
                "scope": self.scope_name,
                "agent_id": self.scope_kwargs.get("agent_id"),
                "raw": False,
            }
            for item in items
        ]

    def list(self, *, limit: int = 20) -> list[dict[str, Any]]:
        raw_result = self.mem.get_all(top_k=limit, filters=self.scope_kwargs)
        items = raw_result.get("results", []) if isinstance(raw_result, dict) else raw_result
        return [
            {
                "id": item.get("id"),
                "text": item.get("memory") or item.get("text") or "",
                "score": 0.0,
                "scope": self.scope_name,
                "agent_id": self.scope_kwargs.get("agent_id"),
                "raw": False,
            }
            for item in items
        ]
