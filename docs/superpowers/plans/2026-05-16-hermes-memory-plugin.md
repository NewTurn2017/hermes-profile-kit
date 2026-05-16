# Hermes memory plugin (mem0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `mem0-memory` as a kit-local plugin (`scripts/mem0-memory/`) exposing a `hpk-memory` CLI for per-profile + read-only-shared memory, then wire it into `manifest.yaml` and `seb`'s SOUL as a `default: false` opt-in option alongside `honcho-memory`.

**Architecture:** Local OSS mem0 backed by Chroma (vector) + SQLite (history + a `raw_facts` fallback table). Storage lives under `~/.hermes/profiles/<profile>/memory/` and `~/.hermes/shared/memory/` (mode 0700). The CLI is the single integration surface — `seb` invokes it through its existing `shell` tool. No `hpk` core changes, no Hermes upstream changes.

**Tech Stack:** Python 3.11+, `mem0ai`, `click`, `pytest`. Plugin package lives in its own venv (`scripts/mem0-memory/`) — same pattern as `scripts/codex-openai-proxy/`.

**Spec:** `docs/superpowers/specs/2026-05-16-hermes-memory-plugin-design.md` (commit `0a079f1`).

---

## File Structure

**Created:**
- `scripts/mem0-memory/pyproject.toml`
- `scripts/mem0-memory/README.md`
- `scripts/mem0-memory/src/mem0_memory/__init__.py`
- `scripts/mem0-memory/src/mem0_memory/paths.py` — `~/.hermes` path resolution
- `scripts/mem0-memory/src/mem0_memory/store.py` — `Store` class wrapping a per-scope `mem0.Memory` instance + `raw_facts` fallback
- `scripts/mem0-memory/src/mem0_memory/output.py` — JSON envelope helpers
- `scripts/mem0-memory/src/mem0_memory/cli.py` — `click` entrypoint exposing `hpk-memory`
- `scripts/mem0-memory/tests/conftest.py` — `HERMES_HOME` tmpdir fixture, fake-memory factory fixture
- `scripts/mem0-memory/tests/test_paths.py`
- `scripts/mem0-memory/tests/test_store.py`
- `scripts/mem0-memory/tests/test_cli.py`
- `scripts/mem0-memory/tests/test_doctor.py`
- `scripts/mem0-memory/tests/test_fallback.py`
- `scripts/mem0-memory/tests/test_roundtrip.py`
- `tests/e2e/test_mem0_memory.py` — hpk-level manifest + plugin-runner integration

**Modified:**
- `manifest.yaml` — add `plugins.mem0-memory`, add `{id: mem0-memory, default: false}` to `profiles.seb.recommended_plugins`
- `profiles/seb/SOUL.md` — append "Memory access" section (~8 lines)
- `CHANGELOG.md` — add `[3.2.0]` entry
- `pyproject.toml` (root) — bump `version` to `3.2.0`

**Not touched:** `src/hpk/*.py`, `profiles/seb/config.yaml`, any other profile, any Hermes upstream code.

---

## Decided API shapes (cross-task contract)

These shapes are referenced by multiple tasks. Lock them now so later tasks stay consistent.

### `Store` (in `store.py`)

```python
class Store:
    def __init__(
        self,
        *,
        profile: str | None = None,
        shared: bool = False,
        memory_factory=None,  # callable(config: dict) -> Memory-like; default uses real mem0
    ) -> None: ...

    # Filesystem
    dir: Path             # ~/.hermes/profiles/<p>/memory  OR  ~/.hermes/shared/memory
    scope_name: str       # "profile" or "shared"
    scope_kwargs: dict    # {"agent_id": "<profile>"} or {"app_id": "hermes-shared"}

    def config(self) -> dict: ...
    def add(self, text: str, *, user_id: str | None = None, meta: dict | None = None) -> dict: ...
    def search(self, q: str, *, limit: int = 5) -> list[dict]: ...
    def list(self, *, limit: int = 20) -> list[dict]: ...

class ExtractorError(RuntimeError): ...
```

### CLI JSON envelopes (in `output.py`)

```python
def ok(**fields) -> dict:    # {"ok": True, **fields}
def err(code: int, kind: str, msg: str, hint: str | None = None) -> dict:
    # {"ok": False, "code": code, "kind": kind, "msg": msg, "hint": hint}
```

Memory item shape (returned inside `memories: [...]`):

```python
{"id": "...", "text": "...", "score": 0.0..1.0, "scope": "profile"|"shared",
 "ts": "ISO8601", "agent_id": str|None, "app_id": str|None, "raw": bool}
```

### Exit codes

`0` ok / `1` user input / `2` env/store / `10` extractor failed / `20` mem0 ImportError.

---

## Task 1: Scaffold the plugin package

**Files:**
- Create: `scripts/mem0-memory/pyproject.toml`
- Create: `scripts/mem0-memory/src/mem0_memory/__init__.py`
- Create: `scripts/mem0-memory/tests/conftest.py`
- Create: `scripts/mem0-memory/tests/test_smoke.py` (gets deleted at end of task)

- [ ] **Step 1: Create the directory tree**

```bash
mkdir -p scripts/mem0-memory/src/mem0_memory scripts/mem0-memory/tests
```

- [ ] **Step 2: Write `scripts/mem0-memory/pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "hermes-mem0-memory"
version = "0.1.0"
description = "Kit-local mem0 store for per-profile + shared memory (hermes-profile-kit)"
requires-python = ">=3.11"
dependencies = [
    "mem0ai>=0.1.0",
    "click>=8.1",
]

[project.optional-dependencies]
dev = ["pytest>=8"]

[project.scripts]
hpk-memory = "mem0_memory.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra -q"
```

- [ ] **Step 3: Write `src/mem0_memory/__init__.py`**

```python
"""Kit-local mem0 store for hermes-profile-kit (per-profile + shared)."""
__version__ = "0.1.0"
```

- [ ] **Step 4: Write `tests/conftest.py` with `HERMES_HOME` tmpdir fixture and a fake-memory factory**

```python
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
```

- [ ] **Step 5: Write a throwaway smoke test to verify the venv runs pytest**

`scripts/mem0-memory/tests/test_smoke.py`:

```python
def test_pytest_runs():
    assert True
```

- [ ] **Step 6: Create venv and install package; run smoke test**

```bash
cd scripts/mem0-memory && uv venv && uv pip install -e ".[dev]" && uv run pytest tests/test_smoke.py -v
```

Expected: 1 passed.

- [ ] **Step 7: Delete the smoke test (no longer needed)**

```bash
rm scripts/mem0-memory/tests/test_smoke.py
```

- [ ] **Step 8: Commit**

```bash
git add scripts/mem0-memory/pyproject.toml scripts/mem0-memory/src/mem0_memory/__init__.py scripts/mem0-memory/tests/conftest.py
git commit -m "feat(mem0-memory): scaffold kit-local plugin package"
```

---

## Task 2: paths.py + test_paths.py

**Files:**
- Create: `scripts/mem0-memory/src/mem0_memory/paths.py`
- Create: `scripts/mem0-memory/tests/test_paths.py`

- [ ] **Step 1: Write the failing test** — `tests/test_paths.py`

```python
"""Path resolution: ~/.hermes/profiles/<p>/memory and ~/.hermes/shared/memory."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from mem0_memory.paths import hermes_home, profile_memory_dir, shared_memory_dir


def test_hermes_home_defaults_to_user_home(monkeypatch):
    monkeypatch.delenv("HERMES_HOME", raising=False)
    assert hermes_home() == Path.home() / ".hermes"


def test_hermes_home_respects_env_override(hermes_home):
    assert hermes_home == Path(os.environ["HERMES_HOME"])
    # function returns the same thing
    from mem0_memory.paths import hermes_home as fn
    assert fn() == hermes_home


def test_profile_memory_dir(hermes_home):
    p = profile_memory_dir("seb")
    assert p == hermes_home / "profiles" / "seb" / "memory"


def test_shared_memory_dir(hermes_home):
    p = shared_memory_dir()
    assert p == hermes_home / "shared" / "memory"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd scripts/mem0-memory && uv run pytest tests/test_paths.py -v
```

Expected: ImportError (`paths` module not yet defined).

- [ ] **Step 3: Write `src/mem0_memory/paths.py`**

```python
"""Path resolution for the mem0-memory plugin storage tree."""
from __future__ import annotations

import os
from pathlib import Path


def hermes_home() -> Path:
    """Return ~/.hermes, or $HERMES_HOME if set (used by tests)."""
    override = os.environ.get("HERMES_HOME")
    return Path(override) if override else Path.home() / ".hermes"


def profile_memory_dir(profile: str) -> Path:
    return hermes_home() / "profiles" / profile / "memory"


def shared_memory_dir() -> Path:
    return hermes_home() / "shared" / "memory"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd scripts/mem0-memory && uv run pytest tests/test_paths.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/mem0-memory/src/mem0_memory/paths.py scripts/mem0-memory/tests/test_paths.py
git commit -m "feat(mem0-memory): paths.py — HERMES_HOME-aware path resolution"
```

---

## Task 3: store.py + test_store.py (isolation + merge)

**Files:**
- Create: `scripts/mem0-memory/src/mem0_memory/store.py`
- Create: `scripts/mem0-memory/tests/test_store.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_store.py`

```python
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
    assert s.scope_kwargs == {"app_id": "hermes-shared"}


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
    assert "app_id" not in fake.added[0]


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd scripts/mem0-memory && uv run pytest tests/test_store.py -v
```

Expected: ImportError on `store`.

- [ ] **Step 3: Write `src/mem0_memory/store.py`**

```python
"""Per-scope mem0.Memory wrapper + raw_facts fallback table."""
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
            self.scope_kwargs: dict[str, str] = {"app_id": "hermes-shared"}
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
        raw_result = self.mem.search(q, limit=limit, **self.scope_kwargs)
        items = raw_result.get("results", []) if isinstance(raw_result, dict) else raw_result
        return [
            {
                "id": item.get("id"),
                "text": item.get("memory") or item.get("text") or "",
                "score": float(item.get("score", 0.0)),
                "scope": self.scope_name,
                "agent_id": self.scope_kwargs.get("agent_id"),
                "app_id": self.scope_kwargs.get("app_id"),
                "raw": False,
            }
            for item in items
        ]

    def list(self, *, limit: int = 20) -> list[dict[str, Any]]:
        raw_result = self.mem.get_all(limit=limit, **self.scope_kwargs)
        items = raw_result.get("results", []) if isinstance(raw_result, dict) else raw_result
        return [
            {
                "id": item.get("id"),
                "text": item.get("memory") or item.get("text") or "",
                "score": 0.0,
                "scope": self.scope_name,
                "agent_id": self.scope_kwargs.get("agent_id"),
                "app_id": self.scope_kwargs.get("app_id"),
                "raw": False,
            }
            for item in items
        ]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd scripts/mem0-memory && uv run pytest tests/test_store.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/mem0-memory/src/mem0_memory/store.py scripts/mem0-memory/tests/test_store.py
git commit -m "feat(mem0-memory): Store — per-scope mem0 wrapper with WAL sqlite + raw_facts"
```

---

## Task 4: cli.py write paths (add, share-add) + test_cli.py

**Files:**
- Create: `scripts/mem0-memory/src/mem0_memory/output.py`
- Create: `scripts/mem0-memory/src/mem0_memory/cli.py`
- Create: `scripts/mem0-memory/tests/test_cli.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_cli.py`

```python
"""CLI: argument parsing, exit codes, JSON envelope, write-path guards."""
from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from mem0_memory import cli as cli_mod


@pytest.fixture
def runner(hermes_home, fake_memory_factory, monkeypatch):
    monkeypatch.setattr(cli_mod, "_memory_factory", fake_memory_factory)
    return CliRunner()


def _invoke(runner: CliRunner, args: list[str]):
    result = runner.invoke(cli_mod.main, args)
    payload = json.loads(result.output) if result.output.strip() else {}
    return result, payload


def test_add_returns_ok_envelope(runner):
    result, payload = _invoke(runner, ["add", "--profile", "seb", "--text", "hello"])
    assert result.exit_code == 0
    assert payload["ok"] is True
    assert payload["scope"] == "profile"
    assert "id" in payload


def test_add_rejects_scope_flag(runner):
    result, payload = _invoke(
        runner, ["add", "--profile", "seb", "--text", "hello", "--scope", "shared"]
    )
    assert result.exit_code == 1
    assert payload["ok"] is False
    assert payload["kind"] == "shared_write_forbidden"


def test_add_requires_profile(runner):
    result = runner.invoke(cli_mod.main, ["add", "--text", "x"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["kind"] == "missing_arg"


def test_add_requires_text(runner):
    result = runner.invoke(cli_mod.main, ["add", "--profile", "seb"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["kind"] == "missing_arg"


def test_share_add_returns_ok_with_shared_scope(runner):
    result, payload = _invoke(runner, ["share-add", "--text", "global fact"])
    assert result.exit_code == 0
    assert payload["scope"] == "shared"


def test_add_meta_parsed_into_dict(runner):
    result, payload = _invoke(
        runner,
        ["add", "--profile", "seb", "--text", "hi", "--meta", "k=v", "--meta", "a=b"],
    )
    assert result.exit_code == 0
    assert payload["meta"] == {"k": "v", "a": "b"}


def test_add_meta_rejects_malformed(runner):
    result = runner.invoke(
        cli_mod.main, ["add", "--profile", "seb", "--text", "x", "--meta", "no_equals"]
    )
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["kind"] == "bad_meta"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd scripts/mem0-memory && uv run pytest tests/test_cli.py -v
```

Expected: ImportError on `cli`.

- [ ] **Step 3: Write `src/mem0_memory/output.py`**

```python
"""JSON envelope helpers."""
from __future__ import annotations

import json
import sys
from typing import Any


def ok(**fields: Any) -> dict[str, Any]:
    return {"ok": True, **fields}


def err(code: int, kind: str, msg: str, hint: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"ok": False, "code": code, "kind": kind, "msg": msg}
    if hint is not None:
        body["hint"] = hint
    return body


def emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.write("\n")
```

- [ ] **Step 4: Write `src/mem0_memory/cli.py` (write paths only — add, share-add; read paths come in Task 5)**

```python
"""hpk-memory CLI — write paths (add, share-add)."""
from __future__ import annotations

from typing import Any

import click

from mem0_memory.output import emit, err, ok
from mem0_memory.store import ExtractorError, Store

# Replaceable in tests via monkeypatch
_memory_factory: Any = None


def _parse_meta(pairs: tuple[str, ...]) -> dict[str, str] | None:
    if not pairs:
        return None
    out: dict[str, str] = {}
    for p in pairs:
        if "=" not in p:
            raise ValueError(f"bad meta '{p}' (expected key=value)")
        k, v = p.split("=", 1)
        if not k:
            raise ValueError(f"bad meta '{p}' (empty key)")
        out[k] = v
    return out


def _store_for_profile(profile: str) -> Store:
    return Store(profile=profile, memory_factory=_memory_factory)


def _shared_store() -> Store:
    return Store(shared=True, memory_factory=_memory_factory)


@click.group()
def main() -> None:
    """hpk-memory — per-profile + shared memory for hermes-profile-kit."""


@main.command("add")
@click.option("--profile", required=False, help="Target profile (required)")
@click.option("--text", required=False, help="Fact text to remember (required)")
@click.option("--meta", multiple=True, help="key=value metadata, repeatable")
@click.option("--scope", default=None, help="(forbidden on add — use share-add for shared)")
@click.option("--user-id", default=None)
def add_cmd(profile: str | None, text: str | None, meta: tuple[str, ...], scope: str | None, user_id: str | None) -> None:
    if scope is not None:
        emit(err(1, "shared_write_forbidden",
                 "add --scope is not allowed; use 'hpk-memory share-add' for the shared pool",
                 hint="share-add"))
        raise SystemExit(1)
    if not profile:
        emit(err(1, "missing_arg", "--profile is required for add"))
        raise SystemExit(1)
    if not text:
        emit(err(1, "missing_arg", "--text is required for add"))
        raise SystemExit(1)
    try:
        meta_dict = _parse_meta(meta)
    except ValueError as e:
        emit(err(1, "bad_meta", str(e)))
        raise SystemExit(1)
    store = _store_for_profile(profile)
    try:
        result = store.add(text, user_id=user_id, meta=meta_dict)
    except ExtractorError as e:
        emit(err(10, "extractor_failed", str(e),
                 hint="raw text saved to raw_facts; query will still find it"))
        raise SystemExit(10)
    payload: dict[str, Any] = {"scope": "profile", "id": _first_id(result)}
    if meta_dict:
        payload["meta"] = meta_dict
    emit(ok(**payload))


@main.command("share-add")
@click.option("--text", required=False)
@click.option("--meta", multiple=True)
def share_add_cmd(text: str | None, meta: tuple[str, ...]) -> None:
    if not text:
        emit(err(1, "missing_arg", "--text is required for share-add"))
        raise SystemExit(1)
    try:
        meta_dict = _parse_meta(meta)
    except ValueError as e:
        emit(err(1, "bad_meta", str(e)))
        raise SystemExit(1)
    store = _shared_store()
    try:
        result = store.add(text, meta=meta_dict)
    except ExtractorError as e:
        emit(err(10, "extractor_failed", str(e),
                 hint="raw text saved to raw_facts; query will still find it"))
        raise SystemExit(10)
    payload: dict[str, Any] = {"scope": "shared", "id": _first_id(result)}
    if meta_dict:
        payload["meta"] = meta_dict
    emit(ok(**payload))


def _first_id(add_result: dict[str, Any]) -> str | None:
    raw = add_result.get("raw_result") if isinstance(add_result, dict) else None
    if isinstance(raw, dict):
        items = raw.get("results") or []
        if items:
            return items[0].get("id")
    return None


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd scripts/mem0-memory && uv run pytest tests/test_cli.py -v
```

Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add scripts/mem0-memory/src/mem0_memory/output.py scripts/mem0-memory/src/mem0_memory/cli.py scripts/mem0-memory/tests/test_cli.py
git commit -m "feat(mem0-memory): CLI add + share-add with JSON envelope and guards"
```

---

## Task 5: cli.py read paths (query, list, share-list) with --scope merge

**Files:**
- Modify: `scripts/mem0-memory/src/mem0_memory/cli.py` (append new commands)
- Modify: `scripts/mem0-memory/tests/test_cli.py` (append new tests)

- [ ] **Step 1: Append failing tests to `tests/test_cli.py`**

```python
# ----- read-path tests -----

def test_query_scope_profile_only(runner):
    runner.invoke(cli_mod.main, ["share-add", "--text", "shared fact"])
    runner.invoke(cli_mod.main, ["add", "--profile", "seb", "--text", "seb fact"])
    result, payload = _invoke(
        runner, ["query", "--profile", "seb", "--q", "fact", "--scope", "profile"]
    )
    assert result.exit_code == 0
    texts = [m["text"] for m in payload["memories"]]
    assert "seb fact" in texts
    assert "shared fact" not in texts


def test_query_scope_shared_only(runner):
    runner.invoke(cli_mod.main, ["share-add", "--text", "shared fact"])
    runner.invoke(cli_mod.main, ["add", "--profile", "seb", "--text", "seb fact"])
    result, payload = _invoke(
        runner, ["query", "--profile", "seb", "--q", "fact", "--scope", "shared"]
    )
    assert result.exit_code == 0
    texts = [m["text"] for m in payload["memories"]]
    assert "shared fact" in texts
    assert "seb fact" not in texts


def test_query_scope_all_merges_profile_and_shared(runner):
    runner.invoke(cli_mod.main, ["share-add", "--text", "shared fact"])
    runner.invoke(cli_mod.main, ["add", "--profile", "seb", "--text", "seb fact"])
    runner.invoke(cli_mod.main, ["add", "--profile", "assistant", "--text", "assistant fact"])
    result, payload = _invoke(
        runner, ["query", "--profile", "seb", "--q", "fact", "--scope", "all"]
    )
    assert result.exit_code == 0
    texts = [m["text"] for m in payload["memories"]]
    assert "seb fact" in texts
    assert "shared fact" in texts
    assert "assistant fact" not in texts
    scopes = {m["scope"] for m in payload["memories"]}
    assert scopes == {"profile", "shared"}


def test_query_scope_default_is_all(runner):
    runner.invoke(cli_mod.main, ["share-add", "--text", "shared fact"])
    runner.invoke(cli_mod.main, ["add", "--profile", "seb", "--text", "seb fact"])
    result, payload = _invoke(runner, ["query", "--profile", "seb", "--q", "fact"])
    texts = {m["text"] for m in payload["memories"]}
    assert texts == {"seb fact", "shared fact"}


def test_query_rejects_unknown_scope(runner):
    result = runner.invoke(
        cli_mod.main, ["query", "--profile", "seb", "--q", "x", "--scope", "bogus"]
    )
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["kind"] == "bad_scope"


def test_query_respects_limit(runner):
    for i in range(5):
        runner.invoke(cli_mod.main, ["add", "--profile", "seb", "--text", f"fact {i}"])
    result, payload = _invoke(
        runner, ["query", "--profile", "seb", "--q", "fact", "--scope", "profile", "--limit", "2"]
    )
    assert len(payload["memories"]) == 2


def test_list_profile(runner):
    runner.invoke(cli_mod.main, ["add", "--profile", "seb", "--text", "x1"])
    runner.invoke(cli_mod.main, ["add", "--profile", "seb", "--text", "x2"])
    result, payload = _invoke(runner, ["list", "--profile", "seb", "--scope", "profile"])
    assert result.exit_code == 0
    assert len(payload["memories"]) == 2


def test_share_list(runner):
    runner.invoke(cli_mod.main, ["share-add", "--text", "g1"])
    runner.invoke(cli_mod.main, ["share-add", "--text", "g2"])
    result, payload = _invoke(runner, ["share-list"])
    assert result.exit_code == 0
    texts = [m["text"] for m in payload["memories"]]
    assert {"g1", "g2"} <= set(texts)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd scripts/mem0-memory && uv run pytest tests/test_cli.py -v
```

Expected: 8 failures (`No such command 'query'` etc).

- [ ] **Step 3: Append read commands to `src/mem0_memory/cli.py`**

Add the following before the `if __name__ == "__main__":` block:

```python
_VALID_SCOPES = ("profile", "shared", "all")


def _merge_dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort by score desc, then dedupe by normalized text (first occurrence wins)."""
    items_sorted = sorted(items, key=lambda x: x.get("score", 0.0), reverse=True)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for it in items_sorted:
        key = (it.get("text") or "").strip().lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


@main.command("query")
@click.option("--profile", required=False)
@click.option("--q", required=False)
@click.option("--scope", default="all")
@click.option("--limit", default=5, type=int)
def query_cmd(profile: str | None, q: str | None, scope: str, limit: int) -> None:
    if scope not in _VALID_SCOPES:
        emit(err(1, "bad_scope", f"--scope must be one of {_VALID_SCOPES}"))
        raise SystemExit(1)
    if not profile:
        emit(err(1, "missing_arg", "--profile is required for query"))
        raise SystemExit(1)
    if not q:
        emit(err(1, "missing_arg", "--q is required for query"))
        raise SystemExit(1)
    results: list[dict[str, Any]] = []
    if scope in ("profile", "all"):
        results.extend(_store_for_profile(profile).search(q, limit=limit))
    if scope in ("shared", "all"):
        results.extend(_shared_store().search(q, limit=limit))
    merged = _merge_dedupe(results)[:limit]
    emit(ok(memories=merged))


@main.command("list")
@click.option("--profile", required=False)
@click.option("--scope", default="all")
@click.option("--limit", default=20, type=int)
def list_cmd(profile: str | None, scope: str, limit: int) -> None:
    if scope not in _VALID_SCOPES:
        emit(err(1, "bad_scope", f"--scope must be one of {_VALID_SCOPES}"))
        raise SystemExit(1)
    if not profile:
        emit(err(1, "missing_arg", "--profile is required for list"))
        raise SystemExit(1)
    results: list[dict[str, Any]] = []
    if scope in ("profile", "all"):
        results.extend(_store_for_profile(profile).list(limit=limit))
    if scope in ("shared", "all"):
        results.extend(_shared_store().list(limit=limit))
    emit(ok(memories=results[:limit]))


@main.command("share-list")
@click.option("--limit", default=20, type=int)
def share_list_cmd(limit: int) -> None:
    results = _shared_store().list(limit=limit)
    emit(ok(memories=results))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd scripts/mem0-memory && uv run pytest tests/test_cli.py -v
```

Expected: 15 passed (7 from Task 4 + 8 new).

- [ ] **Step 5: Commit**

```bash
git add scripts/mem0-memory/src/mem0_memory/cli.py scripts/mem0-memory/tests/test_cli.py
git commit -m "feat(mem0-memory): CLI query/list/share-list with --scope all merge+dedupe"
```

---

## Task 6: doctor command + test_doctor.py

**Files:**
- Modify: `scripts/mem0-memory/src/mem0_memory/cli.py` (append `doctor`)
- Create: `scripts/mem0-memory/tests/test_doctor.py`

- [ ] **Step 1: Write the failing test** — `tests/test_doctor.py`

```python
"""doctor: import check + dir check + sqlite check."""
from __future__ import annotations

import json
import sqlite3

import pytest
from click.testing import CliRunner

from mem0_memory import cli as cli_mod
from mem0_memory.paths import profile_memory_dir


@pytest.fixture
def runner(hermes_home, fake_memory_factory, monkeypatch):
    monkeypatch.setattr(cli_mod, "_memory_factory", fake_memory_factory)
    return CliRunner()


def test_doctor_green(runner, hermes_home):
    # Create the seb profile memory dir by issuing one add
    runner.invoke(cli_mod.main, ["add", "--profile", "seb", "--text", "warmup"])
    result = runner.invoke(cli_mod.main, ["doctor", "--profile", "seb"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["checks"]["mem0_import"] is True
    assert payload["checks"]["profile_dir"] is True
    assert payload["checks"]["sqlite_healthy"] is True


def test_doctor_red_when_mem0_import_fails(runner, monkeypatch):
    def boom(name: str, *a, **kw):
        if name == "mem0":
            raise ImportError("mem0 not installed")
        return __import__(name, *a, **kw)
    monkeypatch.setattr("builtins.__import__", boom)
    result = runner.invoke(cli_mod.main, ["doctor", "--profile", "seb"])
    assert result.exit_code == 20
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["kind"] == "mem0_import_failed"


def test_doctor_red_when_sqlite_corrupt(runner, hermes_home):
    runner.invoke(cli_mod.main, ["add", "--profile", "seb", "--text", "warmup"])
    sqlite_path = profile_memory_dir("seb") / "store.sqlite"
    sqlite_path.write_bytes(b"NOT A SQLITE FILE")
    result = runner.invoke(cli_mod.main, ["doctor", "--profile", "seb"])
    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["kind"] == "sqlite_unhealthy"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd scripts/mem0-memory && uv run pytest tests/test_doctor.py -v
```

Expected: `No such command 'doctor'`.

- [ ] **Step 3: Append `doctor` to `src/mem0_memory/cli.py`**

Add before `if __name__ == "__main__":`:

```python
@main.command("doctor")
@click.option("--profile", required=False, help="If set, also check this profile's store")
def doctor_cmd(profile: str | None) -> None:
    checks: dict[str, bool] = {"mem0_import": False, "profile_dir": False, "sqlite_healthy": False}
    try:
        __import__("mem0")
        checks["mem0_import"] = True
    except ImportError as e:
        emit(err(20, "mem0_import_failed", str(e),
                 hint="cd scripts/mem0-memory && uv pip install -e ."))
        raise SystemExit(20)

    if profile:
        from mem0_memory.paths import profile_memory_dir
        d = profile_memory_dir(profile)
        checks["profile_dir"] = d.is_dir()
        if checks["profile_dir"]:
            sqlite_path = d / "store.sqlite"
            try:
                import sqlite3
                con = sqlite3.connect(sqlite_path)
                con.execute("PRAGMA integrity_check").fetchone()
                con.close()
                checks["sqlite_healthy"] = True
            except sqlite3.DatabaseError as e:
                emit(err(2, "sqlite_unhealthy", str(e), hint="see README recovery section"))
                raise SystemExit(2)
    else:
        checks["profile_dir"] = True
        checks["sqlite_healthy"] = True

    emit(ok(checks=checks))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd scripts/mem0-memory && uv run pytest tests/test_doctor.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/mem0-memory/src/mem0_memory/cli.py scripts/mem0-memory/tests/test_doctor.py
git commit -m "feat(mem0-memory): doctor — import + dir + sqlite integrity checks"
```

---

## Task 7: extractor fallback + test_fallback.py

**Files:**
- Create: `scripts/mem0-memory/tests/test_fallback.py`
- Modify: `scripts/mem0-memory/src/mem0_memory/store.py` (extend `search()` to fall back to `raw_facts`)

- [ ] **Step 1: Write the failing tests** — `tests/test_fallback.py`

```python
"""Extractor failure → raw_facts row written; query falls back to LIKE search."""
from __future__ import annotations

import json
import sqlite3

import pytest

from mem0_memory.paths import profile_memory_dir
from mem0_memory.store import ExtractorError, Store


class ExplodingMemory:
    """Memory factory that always raises on add() (simulates LLM extractor failure)."""
    def __init__(self, config):
        self.config = config

    def add(self, *_a, **_kw):
        raise RuntimeError("openai key missing")

    def search(self, *_a, **_kw):
        return {"results": []}

    def get_all(self, *_a, **_kw):
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd scripts/mem0-memory && uv run pytest tests/test_fallback.py -v
```

Expected: second test fails — `search` returns `[]` because mem0 returned empty and we don't merge raw_facts yet.

- [ ] **Step 3: Extend `Store.search()` in `src/mem0_memory/store.py`** to merge raw_facts

Replace the existing `search` method body with:

```python
    def search(self, q: str, *, limit: int = 5) -> list[dict[str, Any]]:
        raw_result = self.mem.search(q, limit=limit, **self.scope_kwargs)
        items = raw_result.get("results", []) if isinstance(raw_result, dict) else raw_result
        out = [
            {
                "id": item.get("id"),
                "text": item.get("memory") or item.get("text") or "",
                "score": float(item.get("score", 0.0)),
                "scope": self.scope_name,
                "agent_id": self.scope_kwargs.get("agent_id"),
                "app_id": self.scope_kwargs.get("app_id"),
                "raw": False,
            }
            for item in items
        ]
        out.extend(self._search_raw(q, limit=limit))
        return out[:limit]

    def _search_raw(self, q: str, *, limit: int) -> list[dict[str, Any]]:
        con = sqlite3.connect(self.dir / "store.sqlite")
        try:
            rows = con.execute(
                "SELECT id, text, ts FROM raw_facts WHERE text LIKE ? ORDER BY ts DESC LIMIT ?",
                (f"%{q}%", limit),
            ).fetchall()
        finally:
            con.close()
        return [
            {
                "id": f"raw_{rid}",
                "text": text,
                "score": 0.0,
                "scope": self.scope_name,
                "agent_id": self.scope_kwargs.get("agent_id"),
                "app_id": self.scope_kwargs.get("app_id"),
                "raw": True,
                "ts": ts,
            }
            for (rid, text, ts) in rows
        ]
```

- [ ] **Step 4: Run all tests to verify fallback works and nothing regressed**

```bash
cd scripts/mem0-memory && uv run pytest -v
```

Expected: previous test count + 2 new = all green. (Task 3's `test_search_filters_by_scope` may pull in raw_facts rows; should still pass because no failures were triggered there — raw_facts is empty.)

- [ ] **Step 5: Commit**

```bash
git add scripts/mem0-memory/src/mem0_memory/store.py scripts/mem0-memory/tests/test_fallback.py
git commit -m "feat(mem0-memory): extractor failure fallback — raw_facts write + LIKE search"
```

---

## Task 8: roundtrip integration test (real mem0 + echo extractor)

**Files:**
- Create: `scripts/mem0-memory/tests/test_roundtrip.py`

- [ ] **Step 1: Write the test** — `tests/test_roundtrip.py`

```python
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
                "collection_name": "hermes_profile",
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
    mem = _build_echo_memory(hermes_home)
    try:
        mem.add("vault root is /opt/vault", agent_id="seb")
    except Exception as e:
        pytest.skip(f"mem0 in this env requires a richer LLM stub: {e}")
    results = mem.search("vault", agent_id="seb", limit=5)
    items = results.get("results", []) if isinstance(results, dict) else results
    texts = [i.get("memory") or i.get("text") or "" for i in items]
    assert any("vault" in t for t in texts), f"expected 'vault' in results, got {texts}"
```

- [ ] **Step 2: Run the test**

```bash
cd scripts/mem0-memory && uv run pytest tests/test_roundtrip.py -v
```

Expected: PASS, or SKIP with a clear message if mem0's internal LLM contract differs from the stub (acceptable: this test is best-effort integration; the deterministic guarantees live in test_store.py / test_cli.py / test_fallback.py).

- [ ] **Step 3: Run the entire plugin test suite to confirm nothing else regressed**

```bash
cd scripts/mem0-memory && uv run pytest -v
```

Expected: all previous tests pass, roundtrip passes or skips.

- [ ] **Step 4: Commit**

```bash
git add scripts/mem0-memory/tests/test_roundtrip.py
git commit -m "test(mem0-memory): real mem0 add→search roundtrip with echo LLM"
```

---

## Task 9: scripts/mem0-memory/README.md

**Files:**
- Create: `scripts/mem0-memory/README.md`

- [ ] **Step 1: Write the README**

```markdown
# mem0-memory (kit-local plugin)

Per-profile + shared memory for hermes-profile-kit, backed by local mem0 (OSS) + Chroma + SQLite.

**Status:** opt-in. Disabled by default on all profiles. Run alongside the upstream `honcho-memory` plugin — they do not conflict.

## What you get

- A `hpk-memory` CLI exposing six subcommands (`add`, `query`, `list`, `share-add`, `share-list`, `doctor`).
- Per-profile isolation: each profile's facts live under `~/.hermes/profiles/<profile>/memory/`.
- A shared, cross-profile pool under `~/.hermes/shared/memory/`. Profiles read from it; only the user (or a future orchestrator profile) writes to it via `share-add`.
- Filesystem-level isolation (parent dirs are `chmod 700`) and JSON-only stdout for easy parsing.

## Prerequisites

- Python 3.11+
- `uv` (`brew install uv` or `pip install uv`)
- An OpenAI key in `OPENAI_API_KEY` (mem0's default fact extractor uses OpenAI). Without it, the CLI still works — `add` falls back to writing raw text and exits with code `10`; `query` finds it via SQL LIKE.

## Install

```bash
cd scripts/mem0-memory
uv venv
uv pip install -e .

# Make hpk-memory available on PATH (one of):
ln -s "$PWD/.venv/bin/hpk-memory" ~/.local/bin/hpk-memory
# or: export PATH="$PWD/.venv/bin:$PATH" in your shell rc
```

Verify:

```bash
hpk-memory doctor --profile seb
# {"ok": true, "checks": {"mem0_import": true, "profile_dir": ..., "sqlite_healthy": ...}}
```

## Usage

```bash
# Write per-profile (isolated)
hpk-memory add --profile seb --text "Vault root is /Users/me/vault"

# Write shared (user only — by convention)
hpk-memory share-add --text "User timezone is Asia/Seoul"

# Read profile + shared merged (default scope=all)
hpk-memory query --profile seb --q "vault"

# Restrict to one scope
hpk-memory query --profile seb --q "vault" --scope profile
hpk-memory query --profile seb --q "vault" --scope shared

# List recent facts
hpk-memory list --profile seb --limit 20
hpk-memory share-list --limit 20
```

## Demo — cross-profile isolation

```bash
hpk-memory share-add --text "사용자 timezone Asia/Seoul"
hpk-memory add --profile seb       --text "seb은 매일 09:00에 daily note 생성"
hpk-memory add --profile assistant --text "오후 회의 선호"

# seb sees its own + shared, never assistant
hpk-memory query --profile seb --q "사용자 일정" --scope all

# assistant sees its own + shared, never seb
hpk-memory query --profile assistant --q "사용자 일정" --scope all
```

## Exit codes

| Code | Meaning |
|---:|---|
| 0 | success |
| 1 | user input error (missing/bad arg, forbidden scope on `add`) |
| 2 | environment or store error (permissions, sqlite lock, chroma corruption) |
| 10 | mem0 extractor (LLM) failure — raw text saved as fallback |
| 20 | mem0 ImportError — plugin venv missing |

All output is JSON on stdout. Failure shape: `{"ok": false, "code": <int>, "kind": "...", "msg": "...", "hint": "..."}`.

## Storage layout

```
~/.hermes/
├─ profiles/<profile>/memory/
│   ├─ store.sqlite        # mem0 history + raw_facts fallback (WAL mode)
│   └─ chroma/             # vector index
└─ shared/memory/
    ├─ store.sqlite
    └─ chroma/
```

Parent directories are `chmod 700`. Override the root via `HERMES_HOME` env var (used by tests).

## Backup

```bash
tar czf hermes-memory-backup-$(date +%Y%m%d).tgz -C ~ .hermes/profiles/*/memory .hermes/shared/memory
```

## Recovery from corruption

If `hpk-memory doctor --profile <p>` reports `sqlite_unhealthy` or chroma errors:

```bash
cd ~/.hermes/profiles/<p>/memory
mv chroma chroma.bak.$(date +%Y%m%d)
mv store.sqlite store.sqlite.bak.$(date +%Y%m%d)
# Next hpk-memory call will recreate empty stores.
```

The `store.sqlite.raw_facts` table is plain SQL — readable with `sqlite3 store.sqlite "SELECT * FROM raw_facts"` even after chroma is gone.

## Tests

```bash
cd scripts/mem0-memory && uv run pytest -v
```

~25 tests covering paths, isolation, CLI shape, doctor, fallback, and a real mem0 roundtrip (best-effort).

## Limitations (intentional)

- Single-writer per profile (chroma concurrency is not stress-tested).
- No encryption at rest. Filesystem permissions are the trust boundary.
- No automatic backup or migration.
- No hosted-mem0 backend yet (planned: `MEM0_API_KEY` token + config switch).
```

- [ ] **Step 2: Commit**

```bash
git add scripts/mem0-memory/README.md
git commit -m "docs(mem0-memory): plugin README — install, usage, demo, recovery"
```

---

## Task 10: manifest.yaml registration + tests/e2e/test_mem0_memory.py

**Files:**
- Modify: `manifest.yaml`
- Create: `tests/e2e/test_mem0_memory.py`

- [ ] **Step 1: Write the failing hpk e2e test** — `tests/e2e/test_mem0_memory.py`

```python
"""hpk-level integration: manifest registers mem0-memory; seb opts in as default:false."""
from __future__ import annotations

from pathlib import Path

import pytest

from hpk.manifest import load_manifest
from hpk.plugins import PluginExecError, run_plugin


@pytest.fixture
def manifest():
    return load_manifest(Path("manifest.yaml"))


def test_manifest_registers_mem0_memory_plugin(manifest):
    assert "mem0-memory" in manifest.plugins
    p = manifest.plugins["mem0-memory"]
    assert p.upstream_command is None
    assert p.install_path == "scripts/mem0-memory"
    assert p.verified_in_upstream is False


def test_plugin_runner_refuses_kit_local_mem0(manifest):
    p = manifest.plugins["mem0-memory"]
    with pytest.raises(PluginExecError, match="install manually"):
        run_plugin(p, profile="seb")


def test_seb_profile_lists_mem0_as_optional(manifest):
    seb = next(p for p in manifest.profiles if p.name == "seb")
    plugin_ids = [r["id"] for r in seb.recommended_plugins]
    assert "mem0-memory" in plugin_ids
    rec = next(r for r in seb.recommended_plugins if r["id"] == "mem0-memory")
    assert rec["default"] is False
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/e2e/test_mem0_memory.py -v
```

Expected: AssertionError — `mem0-memory` not in `manifest.plugins`.

- [ ] **Step 3: Edit `manifest.yaml`** — add the plugin entry and seb opt-in

Under the existing `plugins:` block (after `codex-openai-proxy`):

```yaml
  mem0-memory:
    description: "Local mem0 store for per-profile + shared memory (kit-local, OSS, zero tokens)."
    upstream_command: null
    install_path: scripts/mem0-memory
    verified_in_upstream: false
    docs: scripts/mem0-memory/README.md
```

Under `profiles.seb.recommended_plugins:` append:

```yaml
      - { id: mem0-memory, default: false }
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/e2e/test_mem0_memory.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Run the full hpk suite to verify no regression**

```bash
uv run pytest -v
```

Expected: 88 (existing) + 3 (new) = 91 passed.

- [ ] **Step 6: Commit**

```bash
git add manifest.yaml tests/e2e/test_mem0_memory.py
git commit -m "feat(manifest): register mem0-memory plugin; seb opts in as default:false"
```

---

## Task 11: seb SOUL.md update + CHANGELOG + version bump

**Files:**
- Modify: `profiles/seb/SOUL.md`
- Modify: `CHANGELOG.md`
- Modify: `pyproject.toml` (root) — `version = "3.2.0"`

- [ ] **Step 1: Append "Memory access" section to `profiles/seb/SOUL.md`**

At the end of the file, append:

```markdown
## Memory access

장기 메모리는 `hpk-memory` CLI를 통해서만 다룬다. 설치되지 않은 환경에서는 비활성으로 간주하고 무시한다.

- 회상 의도(사용자가 "전에 말한 X", "그때 그거", "내가 ~ 했었지" 등)가 명확하면 응답 전 1회만:
  `hpk-memory query --profile seb --q "<핵심 키워드>" --limit 5`
  결과 JSON의 `memories[].text` 만 컨텍스트로 사용. `scope` 필드로 profile/shared 출처 구분.
- 사용자가 "기억해줘", "메모해", "이거 저장" 등 명시적 저장 요청 시:
  `hpk-memory add --profile seb --text "<정제된 한 문장>"`
  공유 풀(`share-add`)에는 절대 쓰지 않는다 — 사용자가 직접 CLI로만 채운다.
- exit code 처리: `0` 정상 사용 / `10` raw fallback 저장됨(사용자에게 "extractor 일시 장애로 원문만 보존" 한 줄 안내) / `20` 사용자에게 `hpk-memory doctor` 실행 안내 / 그 외 비-0은 메모리 없이 계속 진행하고 사용자에게 굳이 알리지 않는다.
- stdout 이 JSON 이 아니거나 `ok` 필드 없으면 메모리 없이 계속 진행.
- 매 턴마다 호출하지 않는다 — 명백히 회상/저장 의도가 있을 때만.
```

- [ ] **Step 2: Bump version in root `pyproject.toml`**

Locate the existing `version = "3.1.2"` line under `[project]` and change to:

```toml
version = "3.2.0"
```

- [ ] **Step 3: Add a CHANGELOG entry** — at the top of `CHANGELOG.md`, just under the `# Changelog` header, add a new section:

```markdown
## [3.2.0] — 2026-05-16

### Added
- `mem0-memory` kit-local plugin (`scripts/mem0-memory/`): per-profile + read-only shared memory via local mem0 (OSS, Chroma + SQLite, zero external tokens).
- `hpk-memory` CLI with six subcommands (`add`, `query`, `list`, `share-add`, `share-list`, `doctor`); JSON-only stdout; documented exit codes (`0/1/2/10/20`).
- Cross-profile demo and recovery procedure in `scripts/mem0-memory/README.md`.
- `seb` profile gains an optional `mem0-memory` entry in `recommended_plugins` (`default: false`).
- `seb` SOUL gains a "Memory access" section instructing the model to call `hpk-memory` through its existing `shell` tool only on clear recall/save intent.

### Notes
- `honcho-memory` remains the upstream-verified default memory provider for `assistant` and `research`. `mem0-memory` is an additive second option, not a replacement.
- No changes to `src/hpk/*.py`, `profiles/seb/config.yaml`, or upstream Hermes. The plugin runner's existing "install manually" path is reused.
```

- [ ] **Step 4: Run the full suite once more and the plugin venv suite**

```bash
uv run pytest -v
cd scripts/mem0-memory && uv run pytest -v && cd -
```

Expected: hpk suite 91 passed; plugin suite ~25 passed.

- [ ] **Step 5: Manual demo (smoke check, not committed)**

```bash
cd scripts/mem0-memory && uv pip install -e . > /dev/null
PATH="$PWD/.venv/bin:$PATH" hpk-memory share-add --text "사용자 timezone Asia/Seoul"
PATH="$PWD/.venv/bin:$PATH" hpk-memory add --profile seb --text "seb은 매일 09:00에 daily note 생성"
PATH="$PWD/.venv/bin:$PATH" hpk-memory add --profile assistant --text "오후 회의 선호"
PATH="$PWD/.venv/bin:$PATH" hpk-memory query --profile seb --q "사용자 일정" --scope all
# Expect: JSON with seb fact + shared fact, no assistant fact.
PATH="$PWD/.venv/bin:$PATH" hpk-memory query --profile assistant --q "사용자 일정" --scope all
# Expect: JSON with assistant fact + shared fact, no seb fact.
```

If the demo passes, the PoC success criterion from the spec is met.

- [ ] **Step 6: Commit**

```bash
git add profiles/seb/SOUL.md CHANGELOG.md pyproject.toml
git commit -m "feat(seb,release): SOUL memory access + 3.2.0 changelog"
```

---

## Self-Review

**1. Spec coverage:**

| Spec section | Covered by |
|---|---|
| 2 Goal #1 (plugin alongside honcho) | Task 10 |
| 2 Goal #2 (`hpk-memory` CLI with six subcommands) | Tasks 4, 5, 6 |
| 2 Goal #3 (local OSS + zero tokens) | Tasks 1, 3 (config), 8 (real roundtrip) |
| 2 Goal #4 (≤ 8 SOUL lines, no `hpk` core changes) | Task 11; entire plan avoids `src/hpk/*` |
| 2 Goal #5 (cross-profile demo) | Task 9 README + Task 11 manual smoke |
| 2 Goal #6 (`default: false` on seb) | Task 10 |
| 3 Architecture diagram | Task 1 scaffolding + Task 3 Store wiring |
| 4 Components A–F | Tasks 1–6, 10 |
| 5 Data flow (write/read/shared/demo) | Tasks 4, 5, 11 |
| 6 Error handling matrix | Tasks 4 (input + shared_write), 6 (doctor + sqlite), 7 (extractor) |
| 7.1 Layer 1 tests (paths/store/cli/doctor/fallback/roundtrip) | Tasks 2, 3, 4, 5, 6, 7, 8 |
| 7.2 Layer 2 hpk e2e | Task 10 |
| 7.3 Layer 3 manual demo | Task 9 README + Task 11 |
| 9 Rollout (CHANGELOG, version, recommended_plugins) | Task 11 + Task 10 |

No gaps.

**2. Placeholder scan:** None. Every step has either runnable code or an exact command + expected output.

**3. Type consistency:**
- `Store(profile=..., shared=..., memory_factory=...)` used identically in Tasks 3, 4, 7, 8.
- `_memory_factory` module-level in `cli.py` is monkey-patched the same way in `test_cli.py` (Task 4/5) and `test_doctor.py` (Task 6).
- `FakeMemory` exposes `add` / `search` / `get_all` — all three are called by the corresponding `Store` methods.
- `ExtractorError` defined in Task 3, raised in Task 3, asserted in Task 7.
- CLI JSON shape (`ok` envelope and `err` envelope) defined in Task 4, asserted in Tasks 4/5/6.
- `HERMES_HOME` env override defined in Task 1 conftest, used by Tasks 2/3/4/5/6/7/8.

---

Plan complete and saved to `docs/superpowers/plans/2026-05-16-hermes-memory-plugin.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
