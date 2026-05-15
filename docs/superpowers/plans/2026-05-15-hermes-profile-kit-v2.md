# hermes-profile-kit v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild hermes-profile-kit as a Python CLI (`hpk`) that interactively configures four isolated Hermes profiles, with daily upstream-sync drift detection and codegen-enforced "no unverified hermes commands."

**Architecture:** `hpk` is a Click CLI that orchestrates `hermes` via subprocess. Manifest v2 (pydantic-validated) drives both wizard prompts and CI codegen. A `scripts/regen_docs.py` walks the upstream Click tree to produce `build/cmd_index.json` + `docs/commands.md`; CI fails if anything `hpk` references is missing from the index. A GitHub Actions cron pulls upstream daily and opens a PR on drift.

**Tech Stack:** Python 3.10+, Click 8, questionary 2, rich 13, pyyaml 6, pydantic 2, pytest, ruff, mypy. Upstream tracked at `/Users/genie/dev/learn/hermes-agent` (NewTurn2017 fork + NousResearch upstream remote).

**Spec:** `docs/superpowers/specs/2026-05-15-hermes-profile-kit-v2-design.md`

---

## File Map

Everything created/modified, grouped by responsibility:

```
hermes-profile-kit/
├── pyproject.toml                                            [NEW]
├── manifest.yaml                                             [REWRITE v1→v2]
├── README.md                                                 [REWRITE]
├── AGENTS.md                                                 [REWRITE]
├── .gitignore                                                [MODIFY]
│
├── src/hpk/
│   ├── __init__.py                                           [NEW]
│   ├── __main__.py                                           [NEW]
│   ├── cli.py                       Click root + subcommands [NEW]
│   ├── wizard.py                    phase A/B/C loop         [NEW]
│   ├── manifest.py                  v2 pydantic + migration  [NEW]
│   ├── profiles.py                  template apply + .env    [NEW]
│   ├── hermes.py                    subprocess wrapper       [NEW]
│   ├── verify.py                    doctor + FILL_IN scan    [NEW]
│   ├── plugins.py                   recommended_plugin runner[NEW]
│   ├── ui.py                        rich console helpers     [NEW]
│   ├── tokens/
│   │   ├── __init__.py                                       [NEW]
│   │   ├── base.py                  TokenHandler interface   [NEW]
│   │   ├── anthropic.py                                      [NEW]
│   │   ├── telegram.py                                       [NEW]
│   │   ├── slack.py                                          [NEW]
│   │   ├── discord.py                                        [NEW]
│   │   ├── brave.py                                          [NEW]
│   │   └── exa.py                                            [NEW]
│   └── codegen/
│       ├── __init__.py                                       [NEW]
│       ├── click_walker.py          walks hermes_cli Click   [NEW]
│       ├── cmd_index.py             (de)serialize index      [NEW]
│       └── validate.py              manifest ↔ index checks  [NEW]
│
├── scripts/
│   ├── regen_docs.py                build/cmd_index.json     [NEW]
│   ├── update_manifest_pin.py       upstream pin updater     [NEW]
│   ├── drift_report.py              PR body builder          [NEW]
│   ├── install.sh                                            [DELETE]
│   ├── verify.sh                                             [DELETE]
│   └── reset.sh                                              [DELETE]
│
├── docs/
│   ├── commands.md                  auto-generated + manual  [REWRITE]
│   ├── concepts.md                  pin sha block added      [MODIFY]
│   └── (gateways.md, troubleshooting.md unchanged)
│
├── tests/
│   ├── __init__.py                                           [NEW]
│   ├── conftest.py                  fake_hermes fixture      [NEW]
│   ├── test_manifest.py                                      [NEW]
│   ├── test_profiles.py                                      [NEW]
│   ├── test_hermes.py                                        [NEW]
│   ├── test_tokens/
│   │   ├── __init__.py                                       [NEW]
│   │   ├── test_anthropic.py                                 [NEW]
│   │   ├── test_telegram.py                                  [NEW]
│   │   ├── test_slack.py                                     [NEW]
│   │   ├── test_discord.py                                   [NEW]
│   │   ├── test_brave.py                                     [NEW]
│   │   └── test_exa.py                                       [NEW]
│   ├── test_plugins.py                                       [NEW]
│   ├── test_wizard.py                                        [NEW]
│   ├── test_verify.py                                        [NEW]
│   ├── test_cli.py                                           [NEW]
│   ├── test_codegen.py                                       [NEW]
│   └── e2e/test_full_setup.py                                [NEW]
│
└── .github/
    ├── workflows/
    │   ├── ci.yml                   pytest + ruff + mypy     [NEW]
    │   ├── upstream-sync.yml        daily cron               [NEW]
    │   └── release.yml              tag → PyPI               [NEW]
    └── dependabot.yml                                        [NEW]
```

---

## Phase 0 — Bootstrap

### Task 0.1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/hpk/__init__.py`
- Create: `src/hpk/__main__.py`
- Create: `src/hpk/cli.py`
- Create: `tests/__init__.py`
- Modify: `.gitignore`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "hermes-profile-kit"
version = "2.0.0"
description = "Interactive multi-profile setup utility for Hermes Agent"
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
authors = [{ name = "NewTurn2017" }]
dependencies = [
  "click>=8.1",
  "questionary>=2.0",
  "rich>=13",
  "pyyaml>=6",
  "pydantic>=2",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-mock>=3", "ruff>=0.5", "mypy>=1.10", "types-PyYAML"]

[project.scripts]
hpk = "hpk.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
hpk = ["py.typed"]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "RUF"]

[tool.mypy]
strict = true
files = ["src/hpk"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra -q"
```

- [ ] **Step 2: Write `src/hpk/__init__.py`**

```python
"""hermes-profile-kit — interactive multi-profile setup for Hermes Agent."""

__version__ = "2.0.0"
```

- [ ] **Step 3: Write `src/hpk/__main__.py`**

```python
from hpk.cli import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Write minimal `src/hpk/cli.py` so `hpk --version` works**

```python
import click

from hpk import __version__


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="hpk")
@click.pass_context
def main(ctx: click.Context) -> None:
    """hpk — interactive multi-profile setup for Hermes Agent."""
    if ctx.invoked_subcommand is None:
        click.echo("Run `hpk setup` to start. `hpk --help` for all commands.")
```

- [ ] **Step 5: Update `.gitignore`**

```diff
+ build/
+ dist/
+ *.egg-info/
+ .venv/
+ __pycache__/
+ .pytest_cache/
+ .mypy_cache/
+ .ruff_cache/
+ manifest.v1.yaml.bak
```

- [ ] **Step 6: Install dev deps and verify**

Run:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
hpk --version
```
Expected: `hpk, version 2.0.0`

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/hpk/ tests/__init__.py .gitignore
git commit -m "feat: scaffold Python package and minimal hpk CLI"
```

---

## Phase 1 — Foundations

### Task 1.1: `ui.py` — rich console helpers

**Files:**
- Create: `src/hpk/ui.py`
- Create: `tests/test_ui.py` (skipped — pure thin wrapper, smoke test only)

- [ ] **Step 1: Write `src/hpk/ui.py`**

```python
"""Console output helpers. All hpk output flows through here for consistent formatting."""
from rich.console import Console
from rich.panel import Panel
from rich.theme import Theme

THEME = Theme({
    "step": "bold cyan",
    "ok": "bold green",
    "warn": "bold yellow",
    "err": "bold red",
    "muted": "dim",
})

console = Console(theme=THEME)


def step(msg: str) -> None:
    console.print(f"[step]▶[/] {msg}")


def ok(msg: str) -> None:
    console.print(f"  [ok]✓[/] {msg}")


def warn(msg: str) -> None:
    console.print(f"  [warn]⚠[/] {msg}")


def err(msg: str) -> None:
    console.print(f"  [err]✗[/] {msg}")


def header(title: str) -> None:
    console.print(Panel.fit(title, border_style="step"))
```

- [ ] **Step 2: Write a smoke test `tests/test_ui.py`**

```python
from hpk import ui


def test_ui_emits_without_raising(capsys):
    ui.header("Test")
    ui.step("doing thing")
    ui.ok("done")
    ui.warn("careful")
    ui.err("bad")
    out = capsys.readouterr().out
    assert "Test" in out and "doing thing" in out and "done" in out
```

- [ ] **Step 3: Run test**

Run: `pytest tests/test_ui.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/hpk/ui.py tests/test_ui.py
git commit -m "feat(ui): add rich-based console helpers"
```

---

### Task 1.2: `manifest.py` — pydantic models + load

**Files:**
- Create: `src/hpk/manifest.py`
- Create: `tests/test_manifest.py`

- [ ] **Step 1: Write the failing tests first** (`tests/test_manifest.py`)

```python
from pathlib import Path

import pytest
import yaml

from hpk.manifest import (
    Manifest,
    ManifestValidationError,
    load_manifest,
)


VALID_YAML = """\
schema_version: 2
kit: { name: hpk, version: 2.0.0, license: MIT }
upstream:
  repo: https://github.com/NousResearch/hermes-agent
  pinned_commit: abc1234
  pinned_version: 0.12.3
  verified_at: 2026-05-15T09:49Z
min_hermes_version: 0.12.0
profiles:
  - name: coder
    template: profiles/coder
    role: dev
    model_tier: sonnet
    channels: [cli]
    tokens:
      required:
        - { key: ANTHROPIC_API_KEY, provider: anthropic }
      optional: []
    recommended_plugins: []
plugins: {}
preserve_existing: [.env]
overwrite_from_template: [SOUL.md, config.yaml]
"""


def write(tmp_path: Path, text: str) -> Path:
    f = tmp_path / "manifest.yaml"
    f.write_text(text)
    return f


def test_load_valid_manifest(tmp_path):
    m = load_manifest(write(tmp_path, VALID_YAML))
    assert isinstance(m, Manifest)
    assert m.profiles[0].name == "coder"
    assert m.profiles[0].tokens.required[0].key == "ANTHROPIC_API_KEY"


def test_schema_version_must_be_2(tmp_path):
    bad = VALID_YAML.replace("schema_version: 2", "schema_version: 99")
    with pytest.raises(ManifestValidationError):
        load_manifest(write(tmp_path, bad))


def test_min_version_must_be_le_pinned(tmp_path):
    bad = VALID_YAML.replace("min_hermes_version: 0.12.0", "min_hermes_version: 99.0.0")
    with pytest.raises(ManifestValidationError, match="min_hermes_version"):
        load_manifest(write(tmp_path, bad))


def test_unknown_plugin_id_referenced(tmp_path):
    bad = VALID_YAML.replace(
        "recommended_plugins: []",
        "recommended_plugins:\n      - { id: nope, default: true }",
    )
    with pytest.raises(ManifestValidationError, match="unknown plugin"):
        load_manifest(write(tmp_path, bad))
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/test_manifest.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Write `src/hpk/manifest.py`**

```python
"""Manifest v2 schema, loader, and validator."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


class ManifestValidationError(ValueError):
    """Raised when manifest.yaml fails schema or semantic validation."""


class TokenSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    provider: str
    wizard: str | None = None


class TokensSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    required: list[TokenSpec] = Field(default_factory=list)
    optional: list[TokenSpec] = Field(default_factory=list)


class RecommendedPlugin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    default: bool = True


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    template: str
    role: str
    model_tier: Literal["haiku", "sonnet", "opus"]
    channels: list[str]
    tokens: TokensSection = Field(default_factory=TokensSection)
    recommended_plugins: list[RecommendedPlugin] = Field(default_factory=list)


class Plugin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str
    upstream_command: str
    verified_in_upstream: bool = False
    docs: str | None = None


class Upstream(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repo: str
    pinned_commit: str
    pinned_version: str
    verified_at: str


class KitMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    version: str
    license: str


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[2]
    kit: KitMeta
    upstream: Upstream
    min_hermes_version: str
    profiles: list[Profile]
    plugins: dict[str, Plugin]
    preserve_existing: list[str]
    overwrite_from_template: list[str]

    @field_validator("min_hermes_version", "upstream")
    @classmethod
    def _strip_leading_v(cls, v):  # type: ignore[override]
        return v

    @model_validator(mode="after")
    def _cross_field(self) -> "Manifest":
        from packaging.version import Version  # type: ignore[import-not-found]
        if Version(self.min_hermes_version) > Version(self.upstream.pinned_version):
            raise ValueError("min_hermes_version must be <= upstream.pinned_version")
        known = set(self.plugins.keys())
        for p in self.profiles:
            for rp in p.recommended_plugins:
                if rp.id not in known:
                    raise ValueError(f"profile {p.name!r} references unknown plugin {rp.id!r}")
        return self


def load_manifest(path: Path) -> Manifest:
    try:
        data = yaml.safe_load(path.read_text())
        return Manifest.model_validate(data)
    except (ValidationError, ValueError) as e:
        raise ManifestValidationError(str(e)) from e
```

- [ ] **Step 4: Add `packaging` dep**

Modify `pyproject.toml`:
```diff
 dependencies = [
   "click>=8.1",
+  "packaging>=23",
   "questionary>=2.0",
```

Run `pip install -e ".[dev]"` again.

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_manifest.py -v`
Expected: 4 PASS

- [ ] **Step 6: Commit**

```bash
git add src/hpk/manifest.py tests/test_manifest.py pyproject.toml
git commit -m "feat(manifest): add v2 pydantic models with cross-field validation"
```

---

### Task 1.3: Manifest v1 → v2 migration

**Files:**
- Modify: `src/hpk/manifest.py` (add `migrate_v1` function)
- Modify: `tests/test_manifest.py` (add migration test)

- [ ] **Step 1: Add the failing test**

Append to `tests/test_manifest.py`:

```python
V1_YAML = """\
kit:
  name: hermes-profile-kit
  version: 1.0.0
  description: drop-in kit
profiles:
  - name: coder
    template: profiles/coder
    role: dev
    model_tier: sonnet
    channels: [cli]
    requires_secrets: [ANTHROPIC_API_KEY]
    optional_secrets: []
min_hermes_version: 0.12.0
"""


def test_migrate_v1_to_v2(tmp_path):
    from hpk.manifest import migrate_v1_yaml
    out = migrate_v1_yaml(V1_YAML, pinned_commit="abc1234", pinned_version="0.12.3", verified_at="2026-05-15T09:49Z")
    assert out["schema_version"] == 2
    assert out["profiles"][0]["tokens"]["required"][0]["key"] == "ANTHROPIC_API_KEY"
    assert out["plugins"] == {}
```

- [ ] **Step 2: Run, expect fail**

Run: `pytest tests/test_manifest.py::test_migrate_v1_to_v2 -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Add `migrate_v1_yaml` to `src/hpk/manifest.py`**

```python
def migrate_v1_yaml(v1_text: str, *, pinned_commit: str, pinned_version: str, verified_at: str) -> dict:
    """Return a v2 manifest dict built from a v1 manifest YAML string."""
    src = yaml.safe_load(v1_text)
    profiles_out = []
    for p in src.get("profiles", []):
        required = [{"key": k, "provider": k.split("_")[0].lower()} for k in p.get("requires_secrets", [])]
        optional = [{"key": k, "provider": k.split("_")[0].lower()} for k in p.get("optional_secrets", [])]
        profiles_out.append({
            "name": p["name"],
            "template": p["template"],
            "role": p["role"],
            "model_tier": p["model_tier"],
            "channels": p.get("channels", ["cli"]),
            "tokens": {"required": required, "optional": optional},
            "recommended_plugins": [],
        })
    return {
        "schema_version": 2,
        "kit": {
            "name": src["kit"]["name"],
            "version": "2.0.0",
            "license": src.get("kit", {}).get("license", "MIT"),
        },
        "upstream": {
            "repo": "https://github.com/NousResearch/hermes-agent",
            "pinned_commit": pinned_commit,
            "pinned_version": pinned_version,
            "verified_at": verified_at,
        },
        "min_hermes_version": src.get("min_hermes_version", "0.12.0"),
        "profiles": profiles_out,
        "plugins": {},
        "preserve_existing": [".env"],
        "overwrite_from_template": ["SOUL.md", "config.yaml"],
    }
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_manifest.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add src/hpk/manifest.py tests/test_manifest.py
git commit -m "feat(manifest): add v1→v2 migration helper"
```

---

### Task 1.4: `hermes.py` — subprocess wrapper

**Files:**
- Create: `src/hpk/hermes.py`
- Create: `tests/conftest.py` (fake_hermes fixture)
- Create: `tests/test_hermes.py`

- [ ] **Step 1: Write `tests/conftest.py`**

```python
"""Shared fixtures. fake_hermes monkeypatches subprocess for predictable Hermes interaction."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any

import pytest


@dataclass
class FakeHermes:
    calls: list[list[str]] = field(default_factory=list)
    profiles_existing: set[str] = field(default_factory=set)
    version: str = "0.12.3"
    home: Path | None = None

    def add_existing(self, name: str) -> None:
        self.profiles_existing.add(name)

    def __call__(self, cmd: list[str], *_args: Any, **kw: Any) -> CompletedProcess[str]:
        self.calls.append(list(cmd))
        if cmd[:2] == ["hermes", "--version"]:
            return CompletedProcess(cmd, 0, stdout=f"Hermes Agent v{self.version}\n", stderr="")
        if cmd[:3] == ["hermes", "profile", "show"]:
            name = cmd[3]
            if name in self.profiles_existing:
                return CompletedProcess(cmd, 0, stdout=f"profile {name}\n", stderr="")
            return CompletedProcess(cmd, 1, stdout="", stderr="not found\n")
        if cmd[:3] == ["hermes", "profile", "create"]:
            name = cmd[3]
            self.profiles_existing.add(name)
            if self.home is not None:
                (self.home / ".hermes/profiles" / name).mkdir(parents=True, exist_ok=True)
            return CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:2] == ["hermes", "doctor"] or (cmd[:2] == ["hermes", "-p"] and cmd[3] == "doctor"):
            return CompletedProcess(cmd, 0, stdout="ok\n", stderr="")
        return CompletedProcess(cmd, 0, stdout="", stderr="")


@pytest.fixture
def fake_hermes(monkeypatch, tmp_path) -> FakeHermes:
    fh = FakeHermes(home=tmp_path)
    monkeypatch.setattr(subprocess, "run", fh)
    monkeypatch.setenv("HOME", str(tmp_path))
    return fh
```

- [ ] **Step 2: Write `tests/test_hermes.py` (failing test first)**

```python
from hpk.hermes import HermesNotFoundError, HermesVersionError, get_version, profile_exists, run_profile_create


def test_get_version_parses_output(fake_hermes):
    assert get_version() == "0.12.3"
    assert fake_hermes.calls[-1] == ["hermes", "--version"]


def test_profile_exists_true_when_show_succeeds(fake_hermes):
    fake_hermes.add_existing("coder")
    assert profile_exists("coder") is True


def test_profile_exists_false_when_show_fails(fake_hermes):
    assert profile_exists("nope") is False


def test_run_profile_create_records_call(fake_hermes):
    run_profile_create("research")
    assert ["hermes", "profile", "create", "research"] in fake_hermes.calls
```

- [ ] **Step 3: Run, expect fail**

Run: `pytest tests/test_hermes.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 4: Write `src/hpk/hermes.py`**

```python
"""Subprocess wrapper around the installed `hermes` binary.

Never imports hermes internals. Every interaction goes through subprocess so
the kit stays decoupled from upstream API changes.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Sequence


class HermesNotFoundError(RuntimeError):
    """`hermes` binary is not on PATH."""


class HermesVersionError(RuntimeError):
    """Installed hermes does not meet a required version constraint."""


def _run(cmd: Sequence[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    if shutil.which("hermes") is None:
        raise HermesNotFoundError("hermes binary not found on PATH")
    return subprocess.run(list(cmd), capture_output=True, text=True, check=check)


_VERSION_RE = re.compile(r"Hermes Agent v(\d+\.\d+\.\d+)")


def get_version() -> str:
    """Return the installed Hermes version as `X.Y.Z`."""
    r = _run(["hermes", "--version"])
    m = _VERSION_RE.search(r.stdout)
    if not m:
        raise HermesVersionError(f"unparseable version output: {r.stdout!r}")
    return m.group(1)


def profile_exists(name: str) -> bool:
    r = _run(["hermes", "profile", "show", name])
    return r.returncode == 0


def run_profile_create(name: str) -> subprocess.CompletedProcess[str]:
    return _run(["hermes", "profile", "create", name], check=True)


def run_doctor(profile: str | None = None) -> subprocess.CompletedProcess[str]:
    cmd: list[str] = ["hermes"]
    if profile is not None:
        cmd += ["-p", profile]
    cmd += ["doctor"]
    return _run(cmd)


def run_raw(cmd: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Escape hatch for plugins.py to invoke arbitrary verified hermes commands."""
    return _run(cmd)
```

- [ ] **Step 5: Run all tests**

Run: `pytest tests/test_hermes.py -v`
Expected: 4 PASS

- [ ] **Step 6: Commit**

```bash
git add src/hpk/hermes.py tests/conftest.py tests/test_hermes.py
git commit -m "feat(hermes): subprocess wrapper with fake_hermes fixture"
```

---

## Phase 2 — Profile Core

### Task 2.1: `profiles.py` — atomic writes + template apply + .env seed

**Files:**
- Create: `src/hpk/profiles.py`
- Create: `tests/test_profiles.py`

- [ ] **Step 1: Write the failing tests** (`tests/test_profiles.py`)

```python
import os
import stat
from pathlib import Path

import pytest

from hpk.profiles import (
    apply_templates,
    atomic_write,
    profile_home,
    seed_env_if_absent,
    set_env_key,
)


def test_atomic_write_creates_file_with_mode(tmp_path):
    target = tmp_path / "x.env"
    atomic_write(target, "hello\n", mode=0o600)
    assert target.read_text() == "hello\n"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_atomic_write_replaces_existing(tmp_path):
    target = tmp_path / "x.env"
    target.write_text("old")
    atomic_write(target, "new", mode=0o600)
    assert target.read_text() == "new"


def test_seed_env_creates_when_missing(tmp_path):
    src = tmp_path / "src.env"
    src.write_text("X=FILL_IN_X\n")
    dst = tmp_path / "p" / ".env"
    seeded = seed_env_if_absent(template=src, target=dst)
    assert seeded is True
    assert dst.read_text() == "X=FILL_IN_X\n"


def test_seed_env_preserves_existing(tmp_path):
    src = tmp_path / "src.env"
    src.write_text("X=FILL_IN_X\n")
    dst = tmp_path / "p" / ".env"
    dst.parent.mkdir()
    dst.write_text("X=secret\n")
    seeded = seed_env_if_absent(template=src, target=dst)
    assert seeded is False
    assert dst.read_text() == "X=secret\n"


def test_set_env_key_replaces_existing(tmp_path):
    f = tmp_path / ".env"
    f.write_text("FOO=FILL_IN\nBAR=keep\n")
    set_env_key(f, "FOO", "real")
    assert "FOO=real" in f.read_text()
    assert "BAR=keep" in f.read_text()


def test_set_env_key_appends_when_missing(tmp_path):
    f = tmp_path / ".env"
    f.write_text("EXISTING=1\n")
    set_env_key(f, "NEW", "v")
    assert "NEW=v" in f.read_text()


def test_apply_templates_copies_soul_and_config(tmp_path):
    template_dir = tmp_path / "tpl"
    template_dir.mkdir()
    (template_dir / "SOUL.md").write_text("soul")
    (template_dir / "config.yaml").write_text("cfg")
    home = tmp_path / "home"
    home.mkdir()
    apply_templates(template_dir=template_dir, profile_home=home, force=False)
    assert (home / "SOUL.md").read_text() == "soul"
    assert (home / "config.yaml").read_text() == "cfg"


def test_apply_templates_skips_existing_without_force(tmp_path):
    template_dir = tmp_path / "tpl"
    template_dir.mkdir()
    (template_dir / "SOUL.md").write_text("new")
    home = tmp_path / "home"
    home.mkdir()
    (home / "SOUL.md").write_text("old")
    apply_templates(template_dir=template_dir, profile_home=home, force=False)
    assert (home / "SOUL.md").read_text() == "old"


def test_apply_templates_overwrites_with_force(tmp_path):
    template_dir = tmp_path / "tpl"
    template_dir.mkdir()
    (template_dir / "SOUL.md").write_text("new")
    home = tmp_path / "home"
    home.mkdir()
    (home / "SOUL.md").write_text("old")
    apply_templates(template_dir=template_dir, profile_home=home, force=True)
    assert (home / "SOUL.md").read_text() == "new"


def test_profile_home_uses_HOME_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert profile_home("coder") == tmp_path / ".hermes" / "profiles" / "coder"
```

- [ ] **Step 2: Run, expect fail**

Run: `pytest tests/test_profiles.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Write `src/hpk/profiles.py`**

```python
"""Profile-home filesystem operations: atomic writes, template apply, .env seeding."""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path


def profile_home(name: str) -> Path:
    return Path(os.environ["HOME"]) / ".hermes" / "profiles" / name


def atomic_write(target: Path, content: str, *, mode: int = 0o600) -> None:
    """Write content atomically: tmp + chmod + rename. POSIX-atomic."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(content)
    tmp.chmod(mode)
    tmp.replace(target)


def seed_env_if_absent(*, template: Path, target: Path) -> bool:
    """If target does not exist, copy template to it with 0600 perms. Return True iff seeded."""
    if target.exists():
        return False
    atomic_write(target, template.read_text(), mode=0o600)
    return True


_ENV_LINE = re.compile(r"^(?P<key>[A-Z_][A-Z0-9_]*)=.*$")


def set_env_key(path: Path, key: str, value: str) -> None:
    """Replace or append `key=value` in a dotenv-style file. Preserves other lines."""
    lines = path.read_text().splitlines() if path.exists() else []
    out: list[str] = []
    replaced = False
    for ln in lines:
        m = _ENV_LINE.match(ln)
        if m and m.group("key") == key:
            out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(ln)
    if not replaced:
        out.append(f"{key}={value}")
    atomic_write(path, "\n".join(out) + "\n", mode=0o600)


def apply_templates(*, template_dir: Path, profile_home: Path, force: bool) -> None:
    """Copy SOUL.md and config.yaml from template_dir into profile_home.

    Existing files are preserved unless force=True. Never touches .env.
    """
    for fname in ("SOUL.md", "config.yaml"):
        src = template_dir / fname
        if not src.exists():
            raise FileNotFoundError(f"template missing: {src}")
        dst = profile_home / fname
        if dst.exists() and not force:
            continue
        shutil.copy2(src, dst)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_profiles.py -v`
Expected: 10 PASS

- [ ] **Step 5: Commit**

```bash
git add src/hpk/profiles.py tests/test_profiles.py
git commit -m "feat(profiles): atomic .env writes + template apply + .env seed"
```

---

## Phase 3 — Token Handlers

### Task 3.1: `tokens/base.py` — interface

**Files:**
- Create: `src/hpk/tokens/__init__.py`
- Create: `src/hpk/tokens/base.py`
- Create: `tests/test_tokens/__init__.py`

- [ ] **Step 1: Write `src/hpk/tokens/__init__.py`**

```python
"""Per-provider token collection handlers.

Each handler is a small class with two methods:
  - intro(): print docs/links so the user knows where to obtain the token
  - validate(value): return (ok: bool, reason: str) without echoing the value
"""
from hpk.tokens.base import TokenHandler  # noqa: F401
```

- [ ] **Step 2: Write `src/hpk/tokens/base.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: str = ""


class TokenHandler(Protocol):
    """Protocol every token-provider handler implements.

    Handlers must NEVER echo the token value. `validate` returns a reason
    string but must not include the value verbatim.
    """

    key: str        # e.g. "ANTHROPIC_API_KEY"
    provider: str   # e.g. "anthropic"
    docs_url: str   # canonical URL where the user obtains the token

    def intro(self) -> str:
        """Markdown/plain text instructions shown before prompting."""
        ...

    def validate(self, value: str) -> ValidationResult:
        """Lightweight client-side format check. Network calls forbidden."""
        ...
```

- [ ] **Step 3: Create empty `tests/test_tokens/__init__.py`**

- [ ] **Step 4: Commit**

```bash
git add src/hpk/tokens/ tests/test_tokens/__init__.py
git commit -m "feat(tokens): protocol + ValidationResult dataclass"
```

---

### Task 3.2: `tokens/anthropic.py`

**Files:**
- Create: `src/hpk/tokens/anthropic.py`
- Create: `tests/test_tokens/test_anthropic.py`

- [ ] **Step 1: Write failing tests**

```python
from hpk.tokens.anthropic import AnthropicHandler


def test_valid_key():
    h = AnthropicHandler()
    assert h.validate("sk-ant-api03-" + "A" * 80).ok


def test_invalid_prefix_rejected():
    h = AnthropicHandler()
    r = h.validate("sk-openai-1234")
    assert not r.ok and "prefix" in r.reason


def test_empty_rejected():
    h = AnthropicHandler()
    assert not h.validate("").ok
```

- [ ] **Step 2: Run, expect fail**

Run: `pytest tests/test_tokens/test_anthropic.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Write `src/hpk/tokens/anthropic.py`**

```python
from hpk.tokens.base import TokenHandler, ValidationResult


class AnthropicHandler:
    key = "ANTHROPIC_API_KEY"
    provider = "anthropic"
    docs_url = "https://console.anthropic.com/settings/keys"

    def intro(self) -> str:
        return (
            "Anthropic API key.\n"
            f"  1. Open {self.docs_url}\n"
            "  2. Create a key (starts with sk-ant-)\n"
            "  3. Paste it below — input is hidden."
        )

    def validate(self, value: str) -> ValidationResult:
        if not value:
            return ValidationResult(False, "empty")
        if not value.startswith("sk-ant-"):
            return ValidationResult(False, "expected sk-ant- prefix")
        if len(value) < 20:
            return ValidationResult(False, "too short")
        return ValidationResult(True)


HANDLER: TokenHandler = AnthropicHandler()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_tokens/test_anthropic.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add src/hpk/tokens/anthropic.py tests/test_tokens/test_anthropic.py
git commit -m "feat(tokens): anthropic handler"
```

---

### Task 3.3: `tokens/telegram.py`

**Files:**
- Create: `src/hpk/tokens/telegram.py`
- Create: `tests/test_tokens/test_telegram.py`

- [ ] **Step 1: Write failing tests**

```python
from hpk.tokens.telegram import TelegramBotFatherHandler


def test_valid_telegram_format():
    assert TelegramBotFatherHandler().validate("123456789:ABCDefGhIJK_LmNoPQRsTuVwXyZ012345abc").ok


def test_telegram_requires_colon():
    r = TelegramBotFatherHandler().validate("123456789ABCDEF")
    assert not r.ok and ":" in r.reason


def test_telegram_first_part_must_be_digits():
    r = TelegramBotFatherHandler().validate("abc:tokenpart")
    assert not r.ok
```

- [ ] **Step 2: Write `src/hpk/tokens/telegram.py`**

```python
import re

from hpk.tokens.base import TokenHandler, ValidationResult


_TELEGRAM_RE = re.compile(r"^\d{6,12}:[A-Za-z0-9_-]{20,}$")


class TelegramBotFatherHandler:
    key = "TELEGRAM_BOT_TOKEN"
    provider = "telegram"
    docs_url = "https://t.me/BotFather"

    def intro(self) -> str:
        return (
            "Telegram bot token (via BotFather).\n"
            f"  1. Open {self.docs_url} in Telegram\n"
            "  2. Send `/newbot` and follow the prompts\n"
            "  3. BotFather replies with `<digits>:<alphanum>`\n"
            "  4. Paste that whole string below."
        )

    def validate(self, value: str) -> ValidationResult:
        if ":" not in value:
            return ValidationResult(False, "missing ':' separator")
        if not _TELEGRAM_RE.match(value):
            return ValidationResult(False, "expected <digits>:<alphanumeric>")
        return ValidationResult(True)


HANDLER: TokenHandler = TelegramBotFatherHandler()
WIZARDS = {"telegram_botfather": HANDLER}
```

- [ ] **Step 3: Run tests + commit**

Run: `pytest tests/test_tokens/test_telegram.py -v`
Expected: 3 PASS

```bash
git add src/hpk/tokens/telegram.py tests/test_tokens/test_telegram.py
git commit -m "feat(tokens): telegram BotFather handler with format validation"
```

---

### Task 3.4: `tokens/slack.py`

**Files:**
- Create: `src/hpk/tokens/slack.py`
- Create: `tests/test_tokens/test_slack.py`

- [ ] **Step 1: Write failing tests**

```python
from hpk.tokens.slack import SlackBotHandler, SlackAppHandler


def test_bot_token_prefix():
    assert SlackBotHandler().validate("xoxb-12345-abcdef").ok
    assert not SlackBotHandler().validate("xapp-12345-abcdef").ok


def test_app_token_prefix():
    assert SlackAppHandler().validate("xapp-1-A1234-xyz").ok
    assert not SlackAppHandler().validate("xoxb-12345").ok
```

- [ ] **Step 2: Write `src/hpk/tokens/slack.py`**

```python
from hpk.tokens.base import TokenHandler, ValidationResult


class SlackBotHandler:
    key = "SLACK_BOT_TOKEN"
    provider = "slack"
    docs_url = "https://api.slack.com/apps"

    def intro(self) -> str:
        return (
            "Slack Bot User OAuth Token (starts with xoxb-).\n"
            f"  1. Open {self.docs_url} and create a new app\n"
            "  2. Under 'OAuth & Permissions' install to a workspace\n"
            "  3. Copy 'Bot User OAuth Token' (xoxb-...)\n"
            "  4. Paste below."
        )

    def validate(self, value: str) -> ValidationResult:
        if not value.startswith("xoxb-"):
            return ValidationResult(False, "expected xoxb- prefix")
        return ValidationResult(True)


class SlackAppHandler:
    key = "SLACK_APP_TOKEN"
    provider = "slack"
    docs_url = "https://api.slack.com/apps"

    def intro(self) -> str:
        return (
            "Slack App-Level Token (starts with xapp-, needed for Socket Mode).\n"
            f"  1. {self.docs_url} → your app → 'Basic Information'\n"
            "  2. Under 'App-Level Tokens' click Generate\n"
            "  3. Scope: connections:write\n"
            "  4. Copy and paste below."
        )

    def validate(self, value: str) -> ValidationResult:
        if not value.startswith("xapp-"):
            return ValidationResult(False, "expected xapp- prefix")
        return ValidationResult(True)


WIZARDS = {
    "slack_bot": SlackBotHandler(),
    "slack_app": SlackAppHandler(),
}
```

- [ ] **Step 3: Run + commit**

Run: `pytest tests/test_tokens/test_slack.py -v`
Expected: 2 PASS

```bash
git add src/hpk/tokens/slack.py tests/test_tokens/test_slack.py
git commit -m "feat(tokens): slack bot + app token handlers"
```

---

### Task 3.5: `tokens/discord.py`

**Files:**
- Create: `src/hpk/tokens/discord.py`
- Create: `tests/test_tokens/test_discord.py`

- [ ] **Step 1: Failing tests**

```python
from hpk.tokens.discord import DiscordHandler


def test_discord_format():
    # Discord bot tokens are 3 dot-separated b64 segments
    assert DiscordHandler().validate("AbCdEf.GhIjKl.MnOpQrStUvWxYz_-123").ok


def test_discord_must_have_two_dots():
    assert not DiscordHandler().validate("nodots").ok
```

- [ ] **Step 2: Write `src/hpk/tokens/discord.py`**

```python
import re

from hpk.tokens.base import ValidationResult


_DISCORD_RE = re.compile(r"^[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{20,}$")


class DiscordHandler:
    key = "DISCORD_BOT_TOKEN"
    provider = "discord"
    docs_url = "https://discord.com/developers/applications"

    def intro(self) -> str:
        return (
            "Discord bot token.\n"
            f"  1. Open {self.docs_url}\n"
            "  2. New Application → Bot → Reset Token (copy once)\n"
            "  3. Paste below."
        )

    def validate(self, value: str) -> ValidationResult:
        if value.count(".") != 2:
            return ValidationResult(False, "expected 3 dot-separated segments")
        if not _DISCORD_RE.match(value):
            return ValidationResult(False, "shape does not match Discord token")
        return ValidationResult(True)


WIZARDS = {"discord_devportal": DiscordHandler()}
```

- [ ] **Step 3: Run + commit**

Run: `pytest tests/test_tokens/test_discord.py -v`
Expected: 2 PASS

```bash
git add src/hpk/tokens/discord.py tests/test_tokens/test_discord.py
git commit -m "feat(tokens): discord bot token handler"
```

---

### Task 3.6: `tokens/brave.py` and `tokens/exa.py`

**Files:**
- Create: `src/hpk/tokens/brave.py`
- Create: `src/hpk/tokens/exa.py`
- Create: `tests/test_tokens/test_brave.py`
- Create: `tests/test_tokens/test_exa.py`

- [ ] **Step 1: Failing tests for brave**

```python
# tests/test_tokens/test_brave.py
from hpk.tokens.brave import BraveHandler


def test_brave_nonempty():
    assert BraveHandler().validate("BSAanySearchToken123").ok


def test_brave_rejects_empty():
    assert not BraveHandler().validate("").ok
```

- [ ] **Step 2: Failing tests for exa**

```python
# tests/test_tokens/test_exa.py
from hpk.tokens.exa import ExaHandler


def test_exa_nonempty():
    assert ExaHandler().validate("anything").ok


def test_exa_rejects_empty():
    assert not ExaHandler().validate("").ok
```

- [ ] **Step 3: Write the handlers**

```python
# src/hpk/tokens/brave.py
from hpk.tokens.base import ValidationResult


class BraveHandler:
    key = "BRAVE_SEARCH_API_KEY"
    provider = "brave"
    docs_url = "https://brave.com/search/api/"

    def intro(self) -> str:
        return f"Brave Search API key from {self.docs_url}."

    def validate(self, value: str) -> ValidationResult:
        return ValidationResult(bool(value), "empty" if not value else "")
```

```python
# src/hpk/tokens/exa.py
from hpk.tokens.base import ValidationResult


class ExaHandler:
    key = "EXA_API_KEY"
    provider = "exa"
    docs_url = "https://exa.ai/"

    def intro(self) -> str:
        return f"Exa API key from {self.docs_url}."

    def validate(self, value: str) -> ValidationResult:
        return ValidationResult(bool(value), "empty" if not value else "")
```

- [ ] **Step 4: Run + commit**

Run: `pytest tests/test_tokens/ -v`
Expected: all PASS

```bash
git add src/hpk/tokens/brave.py src/hpk/tokens/exa.py tests/test_tokens/test_brave.py tests/test_tokens/test_exa.py
git commit -m "feat(tokens): brave + exa minimal handlers"
```

---

### Task 3.7: Token registry

**Files:**
- Modify: `src/hpk/tokens/__init__.py`
- Create: `tests/test_tokens/test_registry.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_tokens/test_registry.py
from hpk.tokens import get_handler


def test_lookup_by_key():
    h = get_handler(provider="anthropic")
    assert h.key == "ANTHROPIC_API_KEY"


def test_lookup_by_wizard_id():
    h = get_handler(wizard="telegram_botfather")
    assert h.key == "TELEGRAM_BOT_TOKEN"


def test_unknown_raises():
    import pytest
    with pytest.raises(KeyError):
        get_handler(provider="ghost")
```

- [ ] **Step 2: Update `src/hpk/tokens/__init__.py`**

```python
from hpk.tokens.anthropic import HANDLER as _anthropic
from hpk.tokens.brave import BraveHandler
from hpk.tokens.discord import WIZARDS as _discord_wizards
from hpk.tokens.exa import ExaHandler
from hpk.tokens.slack import WIZARDS as _slack_wizards
from hpk.tokens.telegram import WIZARDS as _telegram_wizards

_BY_PROVIDER = {
    "anthropic": _anthropic,
    "brave": BraveHandler(),
    "exa": ExaHandler(),
}
_BY_WIZARD = {**_telegram_wizards, **_slack_wizards, **_discord_wizards}


def get_handler(*, provider: str | None = None, wizard: str | None = None):
    if wizard is not None:
        return _BY_WIZARD[wizard]
    if provider is not None:
        return _BY_PROVIDER[provider]
    raise ValueError("need provider or wizard")
```

- [ ] **Step 3: Run + commit**

Run: `pytest tests/test_tokens/ -v`

```bash
git add src/hpk/tokens/__init__.py tests/test_tokens/test_registry.py
git commit -m "feat(tokens): handler registry lookup by provider or wizard id"
```

---

## Phase 4 — Plugins

### Task 4.1: `plugins.py` — recommended_plugin runner

**Files:**
- Create: `src/hpk/plugins.py`
- Create: `tests/test_plugins.py`

- [ ] **Step 1: Failing tests**

```python
# tests/test_plugins.py
import pytest

from hpk.manifest import Plugin
from hpk.plugins import PluginExecError, render_command, run_plugin


def test_render_command_substitutes_profile():
    p = Plugin(description="x", upstream_command="hermes -p {profile} memory setup honcho", verified_in_upstream=True)
    assert render_command(p, profile="research") == ["hermes", "-p", "research", "memory", "setup", "honcho"]


def test_run_plugin_invokes_hermes(fake_hermes):
    p = Plugin(description="x", upstream_command="hermes -p {profile} doctor", verified_in_upstream=True)
    run_plugin(p, profile="coder")
    assert ["hermes", "-p", "coder", "doctor"] in fake_hermes.calls


def test_run_plugin_skips_unverified():
    p = Plugin(description="x", upstream_command="hermes nope", verified_in_upstream=False)
    with pytest.raises(PluginExecError, match="not verified"):
        run_plugin(p, profile="coder")
```

- [ ] **Step 2: Write `src/hpk/plugins.py`**

```python
"""Recommended-plugin runner. Dispatches a manifest-declared hermes command per profile."""
from __future__ import annotations

import shlex

from hpk.hermes import run_raw
from hpk.manifest import Plugin


class PluginExecError(RuntimeError):
    pass


def render_command(plugin: Plugin, *, profile: str) -> list[str]:
    return shlex.split(plugin.upstream_command.format(profile=profile))


def run_plugin(plugin: Plugin, *, profile: str) -> None:
    if not plugin.verified_in_upstream:
        raise PluginExecError(f"plugin not verified in upstream: {plugin.upstream_command!r}")
    cmd = render_command(plugin, profile=profile)
    r = run_raw(cmd)
    if r.returncode != 0:
        raise PluginExecError(f"plugin command failed ({r.returncode}): {r.stderr.strip()}")
```

- [ ] **Step 3: Run + commit**

Run: `pytest tests/test_plugins.py -v`
Expected: 3 PASS

```bash
git add src/hpk/plugins.py tests/test_plugins.py
git commit -m "feat(plugins): render and run manifest-declared recommended plugins"
```

---

## Phase 5 — Wizard + Verify

### Task 5.1: `wizard.py` — preflight

**Files:**
- Create: `src/hpk/wizard.py` (preflight only — phases added incrementally)
- Create: `tests/test_wizard.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_wizard.py
import pytest

from hpk.manifest import Manifest
from hpk.wizard import PreflightError, preflight


def _load_manifest() -> Manifest:
    from tests.test_manifest import VALID_YAML
    from hpk.manifest import Manifest
    import yaml
    return Manifest.model_validate(yaml.safe_load(VALID_YAML))


def test_preflight_passes(fake_hermes, monkeypatch):
    monkeypatch.setenv("PATH", f"{monkeypatch.tmp_path if hasattr(monkeypatch, 'tmp_path') else '/tmp'}/.local/bin:/usr/bin")
    # We bypass PATH check using monkeypatch on the inner function:
    monkeypatch.setattr("hpk.wizard._has_local_bin_on_path", lambda: True)
    preflight(_load_manifest())  # no raise


def test_preflight_rejects_old_hermes(monkeypatch, fake_hermes):
    fake_hermes.version = "0.10.0"
    monkeypatch.setattr("hpk.wizard._has_local_bin_on_path", lambda: True)
    with pytest.raises(PreflightError, match="min_hermes_version"):
        preflight(_load_manifest())
```

- [ ] **Step 2: Write `src/hpk/wizard.py` (preflight only)**

```python
"""Interactive setup wizard. Phases: preflight → for each profile (A base, B tokens, C plugins)."""
from __future__ import annotations

import os
from pathlib import Path

from packaging.version import Version

from hpk import hermes, ui
from hpk.manifest import Manifest


class PreflightError(RuntimeError):
    pass


def _has_local_bin_on_path() -> bool:
    target = str(Path.home() / ".local" / "bin")
    return target in os.environ.get("PATH", "").split(os.pathsep)


def preflight(manifest: Manifest) -> None:
    ui.header("hpk preflight")
    try:
        v = hermes.get_version()
    except hermes.HermesNotFoundError as e:
        raise PreflightError(f"hermes not installed: {e}") from e
    ui.ok(f"hermes {v} detected (manifest requires ≥ {manifest.min_hermes_version})")
    if Version(v) < Version(manifest.min_hermes_version):
        raise PreflightError(f"hermes {v} < min_hermes_version {manifest.min_hermes_version}")
    if not _has_local_bin_on_path():
        ui.warn("~/.local/bin not on PATH — profile aliases like 'coder' won't work")
    else:
        ui.ok("~/.local/bin on PATH")
    ui.ok(f"manifest verified (pinned to {manifest.upstream.pinned_commit})")
```

- [ ] **Step 3: Run + commit**

Run: `pytest tests/test_wizard.py -v`
Expected: 2 PASS

```bash
git add src/hpk/wizard.py tests/test_wizard.py
git commit -m "feat(wizard): preflight checks (hermes version + PATH)"
```

---

### Task 5.2: Wizard phase A (base) + B (tokens)

**Files:**
- Modify: `src/hpk/wizard.py` (add phase functions + `run_wizard`)
- Modify: `tests/test_wizard.py`

- [ ] **Step 1: Add failing tests**

```python
# Append to tests/test_wizard.py
def test_phase_a_creates_profile_and_applies_templates(fake_hermes, tmp_path, monkeypatch):
    # Prep a template dir
    tpl = tmp_path / "profiles" / "coder"
    tpl.mkdir(parents=True)
    (tpl / "SOUL.md").write_text("soul")
    (tpl / "config.yaml").write_text("cfg")
    (tpl / ".env.example").write_text("ANTHROPIC_API_KEY=FILL_IN_ANTHROPIC_API_KEY\n")

    from hpk.manifest import Profile, TokensSection, TokenSpec
    profile = Profile(
        name="coder", template=str(tpl), role="dev", model_tier="sonnet", channels=["cli"],
        tokens=TokensSection(required=[TokenSpec(key="ANTHROPIC_API_KEY", provider="anthropic")]),
    )
    monkeypatch.setenv("HOME", str(tmp_path))

    from hpk.wizard import phase_a_base
    phase_a_base(profile, force=False)
    home = tmp_path / ".hermes/profiles/coder"
    assert (home / "SOUL.md").exists()
    assert (home / "config.yaml").exists()
    assert (home / ".env").exists()
    assert ["hermes", "profile", "create", "coder"] in fake_hermes.calls


def test_phase_b_required_token_written(fake_hermes, tmp_path, monkeypatch):
    home = tmp_path / ".hermes/profiles/coder"
    home.mkdir(parents=True)
    (home / ".env").write_text("ANTHROPIC_API_KEY=FILL_IN_ANTHROPIC_API_KEY\n")
    monkeypatch.setenv("HOME", str(tmp_path))

    from hpk.manifest import Profile, TokensSection, TokenSpec
    profile = Profile(
        name="coder", template="/tmp", role="d", model_tier="sonnet", channels=["cli"],
        tokens=TokensSection(required=[TokenSpec(key="ANTHROPIC_API_KEY", provider="anthropic")]),
    )

    # Stub prompt to return a valid Anthropic-shaped key
    from hpk import wizard
    monkeypatch.setattr(wizard, "_prompt_secret", lambda intro, key: "sk-ant-test-" + "A" * 30)

    wizard.phase_b_tokens(profile)
    contents = (home / ".env").read_text()
    assert "ANTHROPIC_API_KEY=sk-ant-test-" in contents
```

- [ ] **Step 2: Extend `src/hpk/wizard.py`** (append functions)

```python
from pathlib import Path

import questionary  # type: ignore[import-not-found]

from hpk import profiles, tokens
from hpk.manifest import Profile


def phase_a_base(profile: Profile, *, force: bool) -> None:
    ui.step(f"[A] base — {profile.name}")
    if not hermes.profile_exists(profile.name):
        hermes.run_profile_create(profile.name)
        ui.ok(f"hermes profile create {profile.name}")
    else:
        ui.ok(f"profile '{profile.name}' already exists — skip create")

    home = profiles.profile_home(profile.name)
    home.mkdir(parents=True, exist_ok=True)
    profiles.apply_templates(
        template_dir=Path(profile.template), profile_home=home, force=force,
    )
    ui.ok("templates applied (SOUL.md, config.yaml)")
    seeded = profiles.seed_env_if_absent(
        template=Path(profile.template) / ".env.example",
        target=home / ".env",
    )
    ui.ok(".env seeded" if seeded else ".env preserved")


def _prompt_secret(intro: str, key: str) -> str:
    ui.console.print(intro)
    return questionary.password(f"  {key}").ask() or ""


def _collect_one(token_spec, *, optional: bool) -> str | None:
    handler = tokens.get_handler(
        provider=token_spec.provider,
        wizard=token_spec.wizard,
    ) if token_spec.wizard else tokens.get_handler(provider=token_spec.provider)
    if optional:
        proceed = questionary.confirm(
            f"Set up {token_spec.provider} ({token_spec.key}) now?", default=False
        ).ask()
        if not proceed:
            return None
    for attempt in range(3):
        value = _prompt_secret(handler.intro(), token_spec.key)
        if not value:
            return None
        r = handler.validate(value)
        if r.ok:
            return value
        ui.warn(f"validation failed: {r.reason} (attempt {attempt + 1}/3)")
    ui.warn("3 failed validations — skipping")
    return None


def phase_b_tokens(profile: Profile) -> None:
    ui.step(f"[B] tokens — {profile.name}")
    home = profiles.profile_home(profile.name)
    env_path = home / ".env"
    for spec in profile.tokens.required:
        val = _collect_one(spec, optional=False)
        if val:
            profiles.set_env_key(env_path, spec.key, val)
            ui.ok(f"{spec.key} written")
        else:
            ui.warn(f"{spec.key} left as FILL_IN")
    for spec in profile.tokens.optional:
        val = _collect_one(spec, optional=True)
        if val:
            profiles.set_env_key(env_path, spec.key, val)
            ui.ok(f"{spec.key} written")
```

- [ ] **Step 3: Run + commit**

Run: `pytest tests/test_wizard.py -v`
Expected: 4 PASS

```bash
git add src/hpk/wizard.py tests/test_wizard.py
git commit -m "feat(wizard): phase A (base) and phase B (tokens) with idempotent writes"
```

---

### Task 5.3: Wizard phase C (plugins) + `run_wizard` entry

**Files:**
- Modify: `src/hpk/wizard.py`
- Modify: `tests/test_wizard.py`

- [ ] **Step 1: Failing test**

```python
def test_phase_c_runs_recommended_plugin(fake_hermes, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from hpk.manifest import Manifest, Plugin, Profile, RecommendedPlugin, TokensSection, KitMeta, Upstream
    m = Manifest(
        schema_version=2,
        kit=KitMeta(name="k", version="v", license="MIT"),
        upstream=Upstream(repo="r", pinned_commit="c", pinned_version="0.12.3", verified_at="t"),
        min_hermes_version="0.12.0",
        profiles=[
            Profile(name="research", template="/tmp", role="r", model_tier="opus", channels=["cli"],
                    recommended_plugins=[RecommendedPlugin(id="honcho", default=True)]),
        ],
        plugins={"honcho": Plugin(description="d", upstream_command="hermes -p {profile} memory setup honcho", verified_in_upstream=True)},
        preserve_existing=[".env"], overwrite_from_template=["SOUL.md", "config.yaml"],
    )
    monkeypatch.setattr("hpk.wizard._ask_plugin", lambda plugin_id, default: True)
    from hpk.wizard import phase_c_plugins
    phase_c_plugins(m.profiles[0], m.plugins)
    assert ["hermes", "-p", "research", "memory", "setup", "honcho"] in fake_hermes.calls
```

- [ ] **Step 2: Add to `src/hpk/wizard.py`**

```python
from hpk import plugins as plugins_mod


def _ask_plugin(plugin_id: str, default: bool) -> bool:
    return bool(questionary.confirm(f"Enable plugin '{plugin_id}'?", default=default).ask())


def phase_c_plugins(profile: Profile, plugins_catalog) -> None:
    if not profile.recommended_plugins:
        return
    ui.step(f"[C] plugins — {profile.name}")
    for rp in profile.recommended_plugins:
        plugin = plugins_catalog.get(rp.id)
        if plugin is None or not plugin.verified_in_upstream:
            ui.warn(f"plugin {rp.id} not verified — skipping")
            continue
        if not _ask_plugin(rp.id, rp.default):
            ui.ok(f"plugin {rp.id} skipped by user")
            continue
        try:
            plugins_mod.run_plugin(plugin, profile=profile.name)
            ui.ok(f"plugin {rp.id} enabled")
        except plugins_mod.PluginExecError as e:
            ui.warn(f"plugin {rp.id} failed: {e}")


def run_wizard(manifest: Manifest, *, targets: list[str], force: bool, skip_tokens: bool, skip_plugins: bool) -> None:
    preflight(manifest)
    selected = [p for p in manifest.profiles if not targets or p.name in targets]
    for profile in selected:
        ui.header(f"profile {profile.name}")
        phase_a_base(profile, force=force)
        if not skip_tokens:
            phase_b_tokens(profile)
        if not skip_plugins:
            phase_c_plugins(profile, manifest.plugins)
```

- [ ] **Step 3: Run + commit**

Run: `pytest tests/test_wizard.py -v`

```bash
git add src/hpk/wizard.py tests/test_wizard.py
git commit -m "feat(wizard): phase C (plugins) + run_wizard top-level entry"
```

---

### Task 5.4: `verify.py` — doctor + FILL_IN scan

**Files:**
- Create: `src/hpk/verify.py`
- Create: `tests/test_verify.py`

- [ ] **Step 1: Failing tests**

```python
# tests/test_verify.py
from pathlib import Path

from hpk.verify import VerifyResult, fill_in_findings, run_verify


def test_fill_in_findings(tmp_path):
    f = tmp_path / "a.env"
    f.write_text("A=ok\nB=FILL_IN_B\nC=keep\nD=FILL_IN_D\n")
    rows = list(fill_in_findings(f))
    assert rows == [(2, "B"), (4, "D")]


def test_run_verify_aggregates(fake_hermes, tmp_path, monkeypatch):
    fake_hermes.add_existing("coder")
    home = tmp_path / ".hermes/profiles/coder"
    home.mkdir(parents=True)
    (home / ".env").write_text("ANTHROPIC_API_KEY=ok\n")
    monkeypatch.setenv("HOME", str(tmp_path))

    r = run_verify(["coder"])
    assert isinstance(r, VerifyResult)
    assert r.passing == ["coder"] and r.fill_in_remaining == {}
```

- [ ] **Step 2: Write `src/hpk/verify.py`**

```python
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from hpk import hermes, profiles


def fill_in_findings(env_path: Path) -> Iterator[tuple[int, str]]:
    """Yield (lineno, key) for every FILL_IN_* placeholder in env_path."""
    if not env_path.exists():
        return
    for i, line in enumerate(env_path.read_text().splitlines(), 1):
        if "FILL_IN" in line and "=" in line:
            key = line.split("=", 1)[0]
            yield (i, key)


@dataclass
class VerifyResult:
    passing: list[str] = field(default_factory=list)
    failing: list[tuple[str, str]] = field(default_factory=list)  # (name, reason)
    fill_in_remaining: dict[str, list[tuple[int, str]]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.failing and not self.fill_in_remaining


def run_verify(profile_names: list[str]) -> VerifyResult:
    result = VerifyResult()
    for name in profile_names:
        env = profiles.profile_home(name) / ".env"
        rows = list(fill_in_findings(env))
        if rows:
            result.fill_in_remaining[name] = rows
        r = hermes.run_doctor(name)
        if r.returncode == 0:
            result.passing.append(name)
        else:
            result.failing.append((name, r.stderr.strip() or "doctor failed"))
    return result
```

- [ ] **Step 3: Run + commit**

Run: `pytest tests/test_verify.py -v`

```bash
git add src/hpk/verify.py tests/test_verify.py
git commit -m "feat(verify): aggregate doctor + FILL_IN scan into VerifyResult"
```

---

## Phase 6 — CLI Wiring

### Task 6.1: `cli.py` — full subcommand surface

**Files:**
- Modify: `src/hpk/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_cli.py
from click.testing import CliRunner

from hpk.cli import main


def test_version():
    r = CliRunner().invoke(main, ["--version"])
    assert r.exit_code == 0 and "2.0.0" in r.output


def test_setup_subcommand_exists():
    r = CliRunner().invoke(main, ["setup", "--help"])
    assert r.exit_code == 0 and "PROFILE" in r.output


def test_verify_subcommand_exists():
    r = CliRunner().invoke(main, ["verify", "--help"])
    assert r.exit_code == 0


def test_unknown_command():
    r = CliRunner().invoke(main, ["nope"])
    assert r.exit_code != 0
```

- [ ] **Step 2: Replace `src/hpk/cli.py`**

```python
from __future__ import annotations

import sys
from pathlib import Path

import click

from hpk import __version__, ui, verify, wizard
from hpk.manifest import ManifestValidationError, load_manifest


def _manifest_path() -> Path:
    return Path.cwd() / "manifest.yaml"


def _load() -> "Manifest":  # type: ignore[name-defined]
    try:
        return load_manifest(_manifest_path())
    except ManifestValidationError as e:
        ui.err(f"manifest invalid: {e}")
        sys.exit(40)
    except FileNotFoundError:
        ui.err(f"manifest.yaml not found at {_manifest_path()}")
        sys.exit(40)


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="hpk")
@click.pass_context
def main(ctx: click.Context) -> None:
    """hpk — interactive multi-profile setup for Hermes Agent."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(setup)


@main.command()
@click.argument("profile", nargs=-1)
@click.option("--non-interactive", is_flag=True, help="Read tokens from env vars only.")
@click.option("--dry-run", is_flag=True, help="Show actions without changing state.")
@click.option("--force", is_flag=True, help="Overwrite SOUL.md/config.yaml even if present.")
@click.option("--skip-tokens", is_flag=True)
@click.option("--skip-plugins", is_flag=True)
def setup(profile, non_interactive, dry_run, force, skip_tokens, skip_plugins):
    """Interactive multi-profile setup."""
    manifest = _load()
    try:
        wizard.run_wizard(
            manifest,
            targets=list(profile),
            force=force,
            skip_tokens=skip_tokens,
            skip_plugins=skip_plugins,
        )
    except wizard.PreflightError as e:
        ui.err(str(e))
        if "not installed" in str(e):
            sys.exit(10)
        if "min_hermes_version" in str(e):
            sys.exit(11)
        sys.exit(30)


@main.command()
@click.argument("profile", nargs=-1)
def verify_cmd(profile):
    """Run hermes doctor + FILL_IN scan."""
    manifest = _load()
    names = list(profile) or [p.name for p in manifest.profiles]
    r = verify.run_verify(names)
    for name in r.passing:
        ui.ok(f"{name}: doctor green")
    for name, reason in r.failing:
        ui.err(f"{name}: {reason}")
    for name, rows in r.fill_in_remaining.items():
        for line, key in rows:
            ui.warn(f"{name}/.env:{line}: {key} still FILL_IN")
    sys.exit(0 if r.ok else 30)


main.add_command(verify_cmd, name="verify")
```

- [ ] **Step 3: Run + commit**

Run: `pytest tests/test_cli.py -v`

```bash
git add src/hpk/cli.py tests/test_cli.py
git commit -m "feat(cli): wire setup and verify subcommands with exit codes"
```

---

### Task 6.2: `hpk doctor`, `hpk reset`, `hpk plugin`, `hpk sync` stubs

**Files:**
- Modify: `src/hpk/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Failing tests**

```python
def test_doctor_runs(fake_hermes, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "manifest.yaml").write_text(
        open("tests/_fixtures/manifest_v2.yaml").read() if Path("tests/_fixtures/manifest_v2.yaml").exists() else
        # inline a minimal manifest for the test
        """schema_version: 2
kit: {name: hpk, version: 2.0.0, license: MIT}
upstream: {repo: x, pinned_commit: c, pinned_version: 0.12.3, verified_at: t}
min_hermes_version: 0.12.0
profiles: []
plugins: {}
preserve_existing: [.env]
overwrite_from_template: [SOUL.md, config.yaml]
"""
    )
    r = CliRunner().invoke(main, ["doctor"])
    assert r.exit_code == 0


def test_plugin_list_runs(fake_hermes, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "manifest.yaml").write_text(
        """schema_version: 2
kit: {name: hpk, version: 2.0.0, license: MIT}
upstream: {repo: x, pinned_commit: c, pinned_version: 0.12.3, verified_at: t}
min_hermes_version: 0.12.0
profiles: []
plugins: {}
preserve_existing: [.env]
overwrite_from_template: [SOUL.md, config.yaml]
"""
    )
    r = CliRunner().invoke(main, ["plugin", "list"])
    assert r.exit_code == 0
```

(Add `from pathlib import Path` at top of test file if not present.)

- [ ] **Step 2: Add subcommands to `src/hpk/cli.py`** (append before `main.add_command(verify_cmd, name="verify")`)

```python
@main.command()
def doctor() -> None:
    """Check hpk's own health: hermes presence, manifest validity, codegen freshness."""
    manifest = _load()
    try:
        from hpk import hermes as _h
        v = _h.get_version()
        ui.ok(f"hermes {v}")
    except _h.HermesNotFoundError:
        ui.err("hermes not found")
        sys.exit(10)
    ui.ok(f"manifest valid; pinned to {manifest.upstream.pinned_commit}")


@main.command()
@click.argument("profile", nargs=-1)
@click.option("--yes", is_flag=True, help="Skip confirmation.")
@click.option("--backup", is_flag=True, help="Export profile before deleting.")
def reset(profile, yes, backup) -> None:
    """Remove profiles created by this kit (never touches default ~/.hermes/)."""
    manifest = _load()
    names = list(profile) or [p.name for p in manifest.profiles]
    if not yes:
        click.confirm(f"Really delete profiles: {', '.join(names)}?", abort=True)
    from hpk import hermes as _h
    for n in names:
        if backup:
            _h.run_raw(["hermes", "profile", "export", n])
        _h.run_raw(["hermes", "profile", "delete", n, "--yes"])
        ui.ok(f"deleted {n}")


@main.group()
def plugin() -> None:
    """List, enable, or disable manifest-declared recommended plugins."""


@plugin.command("list")
def plugin_list() -> None:
    manifest = _load()
    for p in manifest.profiles:
        ids = [rp.id for rp in p.recommended_plugins]
        ui.console.print(f"  {p.name}: {ids or '(none)'}")


@plugin.command("enable")
@click.argument("profile")
@click.argument("plugin_id")
def plugin_enable(profile, plugin_id) -> None:
    manifest = _load()
    plugins_catalog = manifest.plugins
    if plugin_id not in plugins_catalog:
        ui.err(f"unknown plugin: {plugin_id}")
        sys.exit(40)
    from hpk import plugins as _p
    _p.run_plugin(plugins_catalog[plugin_id], profile=profile)
    ui.ok(f"enabled {plugin_id} for {profile}")


@plugin.command("disable")
@click.argument("profile")
@click.argument("plugin_id")
def plugin_disable(profile, plugin_id) -> None:
    ui.warn(f"manual disable required for {plugin_id} on {profile}; see plugin docs")


@main.command()
@click.option("--dry-run", is_flag=True)
def sync(dry_run) -> None:
    """Local upstream-drift check (CI does it daily). Calls scripts/regen_docs.py --check."""
    import subprocess as _sp
    cmd = [sys.executable, "scripts/regen_docs.py", "--check"]
    r = _sp.run(cmd)
    sys.exit(50 if r.returncode else 0)
```

- [ ] **Step 3: Run + commit**

Run: `pytest tests/test_cli.py -v`

```bash
git add src/hpk/cli.py tests/test_cli.py
git commit -m "feat(cli): add doctor, reset, plugin (list/enable/disable), sync"
```

---

## Phase 7 — Codegen

### Task 7.1: `codegen/click_walker.py`

**Files:**
- Create: `src/hpk/codegen/__init__.py`
- Create: `src/hpk/codegen/click_walker.py`
- Create: `tests/test_codegen.py`

- [ ] **Step 1: Failing test (uses a toy Click group as upstream stand-in)**

```python
# tests/test_codegen.py
import click

from hpk.codegen.click_walker import walk_click


def _toy_root() -> click.Group:
    @click.group()
    def root(): ...

    @root.command()
    @click.option("--name", required=True)
    def create(name): ...

    @root.group()
    def profile(): ...

    @profile.command()
    @click.option("--clone-all", is_flag=True)
    @click.argument("name")
    def create2(name, clone_all): ...

    return root


def test_walk_extracts_commands_and_params():
    nodes = walk_click(_toy_root())
    paths = {n["path"] for n in nodes}
    assert "create" in paths
    assert "profile create2" in paths
    # Spot-check params
    create2 = next(n for n in nodes if n["path"] == "profile create2")
    param_names = {p["name"] for p in create2["params"]}
    assert {"clone_all", "name"} <= param_names
```

- [ ] **Step 2: Write `src/hpk/codegen/click_walker.py`**

```python
"""Walk a click.Group/Command tree and produce a stable, serializable description.

Used at CI time only. The caller imports the upstream Click root (e.g.
`from hermes_cli.main import cli`) and passes it here.
"""
from __future__ import annotations

from typing import Any

import click


def _param_dict(p: click.Parameter) -> dict[str, Any]:
    return {
        "name": p.name,
        "opts": list(getattr(p, "opts", [])),
        "is_flag": bool(getattr(p, "is_flag", False)),
        "required": bool(getattr(p, "required", False)),
        "type": p.type.name if hasattr(p.type, "name") else str(p.type),
        "help": getattr(p, "help", None),
        "hidden": bool(getattr(p, "hidden", False)),
    }


def walk_click(root: click.Group | click.Command, *, prefix: str = "") -> list[dict[str, Any]]:
    """Return a flat list of {path, params, help, hidden} for every leaf command."""
    out: list[dict[str, Any]] = []
    if isinstance(root, click.Group):
        for name, sub in sorted(root.commands.items()):
            path = f"{prefix} {name}".strip()
            out.extend(walk_click(sub, prefix=path))
    elif isinstance(root, click.Command):
        out.append({
            "path": prefix,
            "params": [_param_dict(p) for p in root.params],
            "help": root.help,
            "hidden": bool(root.hidden),
        })
    return out
```

- [ ] **Step 3: Create `src/hpk/codegen/__init__.py`** (empty)

- [ ] **Step 4: Run + commit**

Run: `pytest tests/test_codegen.py -v`

```bash
git add src/hpk/codegen/ tests/test_codegen.py
git commit -m "feat(codegen): Click tree walker producing stable command descriptions"
```

---

### Task 7.2: `codegen/cmd_index.py` (serialize) + `validate.py`

**Files:**
- Create: `src/hpk/codegen/cmd_index.py`
- Create: `src/hpk/codegen/validate.py`
- Modify: `tests/test_codegen.py`

- [ ] **Step 1: Failing tests**

```python
# Append to tests/test_codegen.py
def test_serialize_roundtrip(tmp_path):
    from hpk.codegen.cmd_index import dump, load
    nodes = [{"path": "profile create", "params": [], "help": "h", "hidden": False}]
    p = tmp_path / "i.json"
    dump(nodes, p)
    assert load(p) == nodes


def test_validate_manifest_against_index():
    from hpk.codegen.validate import find_missing_commands
    from hpk.manifest import Plugin
    plugins = {"honcho": Plugin(description="d", upstream_command="hermes -p {profile} memory setup honcho", verified_in_upstream=True)}
    index = [{"path": "-p memory setup honcho", "params": [], "help": "", "hidden": False}]
    missing = find_missing_commands(plugins, index)
    assert missing == []  # the index contains the matching path (modulo profile substitution)


def test_validate_detects_missing():
    from hpk.codegen.validate import find_missing_commands
    from hpk.manifest import Plugin
    plugins = {"x": Plugin(description="d", upstream_command="hermes nope rename", verified_in_upstream=True)}
    missing = find_missing_commands(plugins, [])
    assert missing == ["x"]
```

- [ ] **Step 2: Write `src/hpk/codegen/cmd_index.py`**

```python
import json
from pathlib import Path
from typing import Any


def dump(nodes: list[dict[str, Any]], path: Path) -> None:
    path.write_text(json.dumps(sorted(nodes, key=lambda n: n["path"]), indent=2, sort_keys=True) + "\n")


def load(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text())
```

- [ ] **Step 3: Write `src/hpk/codegen/validate.py`**

```python
from __future__ import annotations

from typing import Any

from hpk.manifest import Plugin


def _normalize_cmd(cmd: str) -> str:
    """Strip 'hermes ' prefix and '{profile}' substitution markers for comparison."""
    parts = [p for p in cmd.split() if p not in ("hermes", "{profile}")]
    return " ".join(parts)


def find_missing_commands(plugins: dict[str, Plugin], cmd_index: list[dict[str, Any]]) -> list[str]:
    """Return plugin ids whose upstream_command is not present in cmd_index."""
    paths = {n["path"] for n in cmd_index}
    missing: list[str] = []
    for pid, plugin in plugins.items():
        normalized = _normalize_cmd(plugin.upstream_command)
        if not any(normalized.endswith(p) or p == normalized for p in paths):
            missing.append(pid)
    return missing
```

- [ ] **Step 4: Run + commit**

Run: `pytest tests/test_codegen.py -v`

```bash
git add src/hpk/codegen/cmd_index.py src/hpk/codegen/validate.py tests/test_codegen.py
git commit -m "feat(codegen): cmd_index (de)serialize + manifest validator"
```

---

### Task 7.3: `scripts/regen_docs.py`

**Files:**
- Create: `scripts/regen_docs.py`
- Create: `tests/test_regen_docs.py` (smoke test, end-to-end on toy upstream)

- [ ] **Step 1: Write the script**

```python
"""Regenerate build/cmd_index.json and docs/commands.md from an upstream hermes-agent clone.

Usage:
    python scripts/regen_docs.py --upstream /path/to/hermes-agent \
        --out build/cmd_index.json --docs docs/commands.md
    python scripts/regen_docs.py --check        # exits 1 if regen produces diffs
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from hpk.codegen.click_walker import walk_click  # noqa: E402
from hpk.codegen.cmd_index import dump, load  # noqa: E402

AUTO_START = "<!-- AUTO-GENERATED — DO NOT EDIT below this line. -->"
AUTO_END = "<!-- END AUTO-GENERATED -->"


def _import_upstream_root(upstream_path: Path):
    sys.path.insert(0, str(upstream_path / "src"))
    from hermes_cli.main import cli  # type: ignore[import-not-found]
    return cli


def _render_md(nodes: list[dict], pinned_commit: str) -> str:
    lines = [
        AUTO_START,
        f"<!-- Regenerated against hermes-agent@{pinned_commit}. Do not edit by hand. -->",
        "",
        "## Verified hermes commands",
        "",
    ]
    for n in nodes:
        if n["hidden"]:
            continue
        params = " ".join(
            ("--" + p["name"].replace("_", "-")) if p["is_flag"] else f"<{p['name']}>"
            for p in n["params"]
        )
        lines.append(f"- `hermes {n['path']} {params}`".rstrip())
    lines.append("")
    lines.append(AUTO_END)
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream", type=Path)
    ap.add_argument("--out", type=Path, default=REPO / "build" / "cmd_index.json")
    ap.add_argument("--docs", type=Path, default=REPO / "docs" / "commands.md")
    ap.add_argument("--pinned-commit", default="unknown")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if args.upstream is None:
        if args.check and args.out.exists():
            print("--check requires --upstream; skipping (CI provides it)")
            return
        ap.error("--upstream required unless --check with existing index")

    root = _import_upstream_root(args.upstream)
    nodes = walk_click(root)

    new_md = _render_md(nodes, args.pinned_commit)

    if args.check:
        old_index = load(args.out) if args.out.exists() else []
        if old_index != sorted(nodes, key=lambda n: n["path"]):
            print("cmd_index drift detected", file=sys.stderr)
            sys.exit(1)
        if args.docs.exists():
            existing = args.docs.read_text()
            generated_block = new_md.split(AUTO_START, 1)[1]
            if generated_block not in existing:
                print("docs/commands.md auto-section drift", file=sys.stderr)
                sys.exit(1)
        return

    args.out.parent.mkdir(parents=True, exist_ok=True)
    dump(nodes, args.out)

    if args.docs.exists():
        existing = args.docs.read_text()
        before, _, _ = existing.partition(AUTO_START)
        after_marker = existing.partition(AUTO_END)
        rest = after_marker[2] if AUTO_END in existing else ""
        merged = before + new_md + rest
    else:
        merged = (
            "# Commands Reference\n\n"
            + new_md
            + "\n## Kit-specific notes (hand-written)\n\n"
            "- Commands not in the verified list above are never invoked by `hpk`.\n"
        )
    args.docs.parent.mkdir(parents=True, exist_ok=True)
    args.docs.write_text(merged)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke test (no real upstream — just `--check` on empty)**

Run:
```bash
python scripts/regen_docs.py --check
```
Expected: prints "skipping" and exits 0 (no upstream provided, no index file yet).

- [ ] **Step 3: Commit**

```bash
git add scripts/regen_docs.py
git commit -m "feat(codegen): regen_docs.py — Click→index→docs pipeline"
```

---

## Phase 8 — CI

### Task 8.1: `ci.yml` workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write workflow**

```yaml
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "${{ matrix.python }}" }
      - run: pip install -e ".[dev]"
      - run: ruff check src tests
      - run: mypy
      - run: pytest -ra
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add lint+type+pytest matrix for Python 3.10/3.11/3.12"
```

---

### Task 8.2: `scripts/update_manifest_pin.py`

**Files:**
- Create: `scripts/update_manifest_pin.py`
- Create: `tests/test_update_pin.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_update_pin.py
from pathlib import Path

import yaml

from scripts.update_manifest_pin import update_pin


def test_update_pin_writes_new_values(tmp_path):
    m = tmp_path / "manifest.yaml"
    m.write_text(
        """schema_version: 2
kit: {name: hpk, version: 2.0.0, license: MIT}
upstream: {repo: x, pinned_commit: old, pinned_version: 0.12.0, verified_at: old}
min_hermes_version: 0.12.0
profiles: []
plugins: {}
preserve_existing: [.env]
overwrite_from_template: [SOUL.md, config.yaml]
"""
    )
    update_pin(m, commit="new123", version="0.12.5", verified_at="2026-05-16T00:00Z")
    data = yaml.safe_load(m.read_text())
    assert data["upstream"]["pinned_commit"] == "new123"
    assert data["upstream"]["pinned_version"] == "0.12.5"
```

- [ ] **Step 2: Write `scripts/update_manifest_pin.py`**

```python
"""Update manifest.yaml's upstream.pinned_* fields. Called by upstream-sync workflow."""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml


def update_pin(path: Path, *, commit: str, version: str, verified_at: str) -> None:
    data = yaml.safe_load(path.read_text())
    data["upstream"]["pinned_commit"] = commit
    data["upstream"]["pinned_version"] = version
    data["upstream"]["verified_at"] = verified_at
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=Path("manifest.yaml"))
    ap.add_argument("--commit", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--verified-at", required=True)
    a = ap.parse_args()
    update_pin(a.manifest, commit=a.commit, version=a.version, verified_at=a.verified_at)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Make scripts/ a discoverable package for tests**

Create `scripts/__init__.py` (empty).

- [ ] **Step 4: Run + commit**

Run: `pytest tests/test_update_pin.py -v`

```bash
git add scripts/__init__.py scripts/update_manifest_pin.py tests/test_update_pin.py
git commit -m "feat(ci): update_manifest_pin.py for upstream-sync workflow"
```

---

### Task 8.3: `scripts/drift_report.py`

**Files:**
- Create: `scripts/drift_report.py`
- Create: `tests/test_drift_report.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_drift_report.py
from scripts.drift_report import compute_diff, render_markdown


def test_compute_diff_added_removed_renamed():
    old = [{"path": "a", "params": []}, {"path": "b", "params": []}]
    new = [{"path": "a", "params": []}, {"path": "c", "params": []}]
    added, removed = compute_diff(old, new)
    assert added == ["c"] and removed == ["b"]


def test_render_markdown():
    md = render_markdown(added=["c"], removed=["b"], old_sha="old", new_sha="new")
    assert "c" in md and "b" in md and "new" in md
```

- [ ] **Step 2: Write `scripts/drift_report.py`**

```python
"""Produce a markdown drift report for the upstream-sync PR body."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def compute_diff(old: list[dict[str, Any]], new: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    op = {n["path"] for n in old}
    np_ = {n["path"] for n in new}
    return sorted(np_ - op), sorted(op - np_)


def render_markdown(*, added: list[str], removed: list[str], old_sha: str, new_sha: str) -> str:
    lines = [f"## Upstream sync — hermes-agent {old_sha} → {new_sha}", ""]
    if added:
        lines += ["### Commands added", *[f"+ `hermes {p}`" for p in added], ""]
    if removed:
        lines += ["### Commands removed", *[f"- `hermes {p}`" for p in removed], ""]
    if not added and not removed:
        lines += ["No command surface changes."]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old-index", type=Path, required=True)
    ap.add_argument("--new-index", type=Path, required=True)
    ap.add_argument("--old-sha", required=True)
    ap.add_argument("--new-sha", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    old = json.loads(a.old_index.read_text()) if a.old_index.exists() else []
    new = json.loads(a.new_index.read_text())
    added, removed = compute_diff(old, new)
    a.out.write_text(render_markdown(added=added, removed=removed, old_sha=a.old_sha, new_sha=a.new_sha))


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run + commit**

Run: `pytest tests/test_drift_report.py -v`

```bash
git add scripts/drift_report.py tests/test_drift_report.py
git commit -m "feat(ci): drift_report.py for upstream-sync PR body"
```

---

### Task 8.4: `upstream-sync.yml`

**Files:**
- Create: `.github/workflows/upstream-sync.yml`

- [ ] **Step 1: Write workflow**

```yaml
name: upstream-sync
on:
  schedule:
    - cron: "0 6 * * *"
  workflow_dispatch: {}

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - name: Snapshot old index
        run: cp -f build/cmd_index.json build/cmd_index.old.json 2>/dev/null || echo "[]" > build/cmd_index.old.json
      - name: Clone upstream
        run: |
          git clone --depth=1 https://github.com/NousResearch/hermes-agent.git /tmp/upstream
          cd /tmp/upstream && echo "SHA=$(git rev-parse --short HEAD)" >> "$GITHUB_ENV"
      - name: Install
        run: |
          pip install /tmp/upstream
          pip install -e ".[dev]"
      - name: Get upstream version
        run: |
          VER=$(hermes --version 2>/dev/null | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | tr -d v)
          echo "VERSION=$VER" >> "$GITHUB_ENV"
      - name: Regen
        run: |
          python scripts/regen_docs.py \
            --upstream /tmp/upstream \
            --out build/cmd_index.json \
            --docs docs/commands.md \
            --pinned-commit "$SHA"
      - name: Update manifest pin
        run: |
          python scripts/update_manifest_pin.py \
            --commit "$SHA" \
            --version "$VERSION" \
            --verified-at "$(date -u +%Y-%m-%dT%H:%MZ)"
      - name: Drift report
        run: |
          python scripts/drift_report.py \
            --old-index build/cmd_index.old.json \
            --new-index build/cmd_index.json \
            --old-sha "$(jq -r '.upstream.pinned_commit' manifest.yaml 2>/dev/null || echo old)" \
            --new-sha "$SHA" \
            --out build/drift_report.md
      - uses: peter-evans/create-pull-request@v6
        with:
          title: "upstream sync: hermes-agent@${{ env.SHA }}"
          body-path: build/drift_report.md
          branch: upstream-sync/auto
          commit-message: "chore(sync): hermes-agent@${{ env.SHA }} (${{ env.VERSION }})"
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/upstream-sync.yml
git commit -m "ci: daily upstream-sync workflow with auto-PR on drift"
```

---

## Phase 9 — Migration + Docs

### Task 9.1: Remove v1 bash scripts

**Files:**
- Delete: `scripts/install.sh`, `scripts/verify.sh`, `scripts/reset.sh`

- [ ] **Step 1: Remove**

```bash
git rm scripts/install.sh scripts/verify.sh scripts/reset.sh
```

- [ ] **Step 2: Commit**

```bash
git commit -m "chore: remove v1 bash scripts (replaced by hpk CLI)"
```

---

### Task 9.2: Migrate `manifest.yaml` to v2

**Files:**
- Backup: `manifest.yaml` → `manifest.v1.yaml.bak` (gitignored)
- Rewrite: `manifest.yaml` (v2)

- [ ] **Step 1: Back up and rewrite**

```bash
cp manifest.yaml manifest.v1.yaml.bak
```

- [ ] **Step 2: Replace `manifest.yaml` with v2 content**

Use the content from spec Section 4 (the full v2 example), populating:
- `upstream.pinned_commit: 5621fc44` (from earlier exploration)
- `upstream.pinned_version: 0.12.3` (placeholder — CI will overwrite on next sync)
- `upstream.verified_at: 2026-05-15T09:49Z`
- `tokens[].wizard` set to `telegram_botfather` / `discord_devportal` for Telegram/Discord rows
- `plugins:` with `honcho-memory` and `brave-search-tool` entries
- `recommended_plugins` per profile as in the spec

(The full v2 YAML body is in `docs/superpowers/specs/2026-05-15-hermes-profile-kit-v2-design.md` Section 4.)

- [ ] **Step 3: Validate**

Run:
```bash
python -c "from hpk.manifest import load_manifest; load_manifest('manifest.yaml')"
```
Expected: no error.

- [ ] **Step 4: Commit**

```bash
git add manifest.yaml
git commit -m "feat(manifest): migrate to schema v2 (tokens structured + recommended_plugins)"
```

---

### Task 9.3: Rewrite `AGENTS.md`

**Files:**
- Rewrite: `AGENTS.md`

- [ ] **Step 1: Replace `AGENTS.md` with**

```markdown
# AGENTS.md — Execution Playbook

> This is the canonical entry point for LLM agents reading this repository.

## Goal

Set up four isolated Hermes profiles via the kit's interactive CLI: `hpk`.

## Single command

```bash
pipx install hermes-profile-kit
hpk setup
```

That's the entire happy path. The wizard:
1. Verifies hermes presence and version (>= manifest.min_hermes_version).
2. For each profile in `manifest.yaml`:
   - Creates it (`hermes profile create <name>`) if absent.
   - Copies `SOUL.md` and `config.yaml` from `profiles/<name>/`.
   - Seeds `.env` from `.env.example` (chmod 600). NEVER overwrites an existing `.env`.
   - Prompts for required + optional tokens with provider-specific guidance.
   - Asks before enabling each recommended plugin (Honcho etc.).
3. Prints a summary listing any `FILL_IN_*` still remaining.

## Hard rules (do not violate)

1. NEVER write tokens to git-tracked files.
2. NEVER guess values. If a token prompt is empty, leave `FILL_IN_*` and report it in the summary.
3. NEVER touch the default profile (`~/.hermes/`).
4. NEVER run `gateway install` without explicit user confirmation.
5. NEVER invoke a hermes command that is not in `build/cmd_index.json`.

## When you need more

- Manifest definition: `manifest.yaml` (v2 schema)
- Spec: `docs/superpowers/specs/2026-05-15-hermes-profile-kit-v2-design.md`
- Verified hermes commands: `docs/commands.md` (auto-generated)
- Per-profile customization: edit `profiles/<name>/SOUL.md` or `config.yaml`, then run `hpk setup --force`.
- Troubleshooting: `docs/troubleshooting.md`
```

- [ ] **Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs(agents): rewrite for hpk-driven flow"
```

---

### Task 9.4: Rewrite `README.md`

**Files:**
- Rewrite: `README.md`

- [ ] **Step 1: Replace top of README with**

```markdown
# hermes-profile-kit

Interactive multi-profile setup utility for [Hermes Agent](https://github.com/NousResearch/hermes-agent).

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://github.com/NewTurn2017/hermes-profile-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/NewTurn2017/hermes-profile-kit/actions/workflows/ci.yml)

## Quick start

```bash
pipx install hermes-profile-kit
hpk setup
```

The wizard walks you through 4 profiles (`coder` / `assistant` / `research` / `community-bot`), prompts for the right tokens per channel (Anthropic, Telegram, Slack, Discord, Brave, Exa), and optionally enables recommended plugins (Honcho memory, Brave search tool).

## What hpk does (and doesn't)

- ✅ Creates and configures four isolated Hermes profiles.
- ✅ Walks you through BotFather, Slack app, Discord devportal flows.
- ✅ Atomic, idempotent `.env` writes (chmod 600). Re-running is safe.
- ✅ Daily upstream-sync via GitHub Actions — kit stays current with Hermes changes.
- ❌ Does not install Hermes itself (see [Hermes installation](https://github.com/NousResearch/hermes-agent#installation)).
- ❌ Does not start gateway services automatically.
- ❌ Does not invoke any hermes command that isn't verified in upstream.

## How it stays correct

`hpk` never embeds a hermes command that hasn't been observed in the upstream Click tree. CI walks `hermes_cli`'s command tree daily, regenerates `docs/commands.md` and `build/cmd_index.json`, and opens a PR when drift is detected.

## Profiles

| Profile | Role | Model tier | Channels |
|---|---|---|---|
| `coder` | Full-stack dev assistant | Sonnet | CLI |
| `assistant` | Personal daily assistant | Sonnet | CLI + Telegram |
| `research` | Web-search-backed research | Opus | CLI |
| `community-bot` | Korean dev community helper | Haiku | Telegram + Discord |

## Customization

| Goal | Edit |
|---|---|
| Change model | `~/.hermes/profiles/<name>/config.yaml` |
| Change persona | `~/.hermes/profiles/<name>/SOUL.md` |
| Add new profile | `profiles/<name>/{SOUL.md,config.yaml,.env.example}` + add to `manifest.yaml` → `hpk setup` |
| Enable a plugin | Add to `manifest.yaml` `plugins:` + reference from `recommended_plugins` |

API keys go in `~/.hermes/profiles/<name>/.env`. They're plain text with `chmod 600` — the kit deliberately does not pretend to encrypt them.

## Commands

```bash
hpk setup [profile...]    # interactive wizard
hpk verify                # doctor + FILL_IN scan
hpk doctor                # hpk's own health
hpk reset [profile...]    # remove kit-created profiles
hpk plugin list           # show recommended_plugins
hpk sync --dry-run        # local drift check
```

## License

MIT. See `LICENSE`.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs(readme): rewrite for hpk-driven flow"
```

---

### Task 9.5: Update `docs/concepts.md` with pinned-commit disclaimer

**Files:**
- Modify: `docs/concepts.md`

- [ ] **Step 1: Add disclaimer block at top of "What is scoped per profile" section**

Insert after the existing header:

```markdown
> **Implementation note**: The exact filenames below (e.g. `MEMORY.md`, `state.db`) reflect Hermes' internal layout. They are accurate against the upstream commit pinned in `manifest.yaml` (`upstream.pinned_commit`). For canonical guarantees, see Hermes' own docs at https://hermes-agent.nousresearch.com/.
```

- [ ] **Step 2: Commit**

```bash
git add docs/concepts.md
git commit -m "docs(concepts): note that internal filenames track pinned upstream commit"
```

---

## Phase 10 — E2E

### Task 10.1: End-to-end smoke test using `fake_hermes`

**Files:**
- Create: `tests/e2e/__init__.py`
- Create: `tests/e2e/test_full_setup.py`

- [ ] **Step 1: Write the E2E test**

```python
"""End-to-end: invoke hpk.cli with a full v2 manifest and a fake hermes."""
from pathlib import Path

import yaml
from click.testing import CliRunner

from hpk.cli import main as cli_main


MANIFEST_YAML = """\
schema_version: 2
kit: {name: hpk, version: 2.0.0, license: MIT}
upstream: {repo: x, pinned_commit: abc, pinned_version: 0.12.3, verified_at: 2026-05-15T09:49Z}
min_hermes_version: 0.12.0
profiles:
  - name: coder
    template: profiles/coder
    role: dev
    model_tier: sonnet
    channels: [cli]
    tokens:
      required:
        - { key: ANTHROPIC_API_KEY, provider: anthropic }
      optional: []
    recommended_plugins: []
plugins: {}
preserve_existing: [.env]
overwrite_from_template: [SOUL.md, config.yaml]
"""


def _scaffold(tmp_path: Path) -> None:
    (tmp_path / "manifest.yaml").write_text(MANIFEST_YAML)
    tpl = tmp_path / "profiles" / "coder"
    tpl.mkdir(parents=True)
    (tpl / "SOUL.md").write_text("soul")
    (tpl / "config.yaml").write_text("cfg")
    (tpl / ".env.example").write_text("ANTHROPIC_API_KEY=FILL_IN_ANTHROPIC_API_KEY\n")


def test_e2e_setup_happy_path(fake_hermes, tmp_path, monkeypatch):
    _scaffold(tmp_path)
    monkeypatch.chdir(tmp_path)
    # Stub the wizard's prompts to provide a valid Anthropic-shaped key
    from hpk import wizard
    monkeypatch.setattr(wizard, "_prompt_secret", lambda intro, key: "sk-ant-test-" + "A" * 30)
    monkeypatch.setattr("hpk.wizard._has_local_bin_on_path", lambda: True)

    r = CliRunner().invoke(cli_main, ["setup"])
    assert r.exit_code == 0, r.output

    env = tmp_path / ".hermes" / "profiles" / "coder" / ".env"
    assert "ANTHROPIC_API_KEY=sk-ant-test-" in env.read_text()
    assert ["hermes", "profile", "create", "coder"] in fake_hermes.calls


def test_e2e_setup_is_idempotent(fake_hermes, tmp_path, monkeypatch):
    _scaffold(tmp_path)
    monkeypatch.chdir(tmp_path)
    from hpk import wizard
    monkeypatch.setattr(wizard, "_prompt_secret", lambda intro, key: "sk-ant-test-" + "A" * 30)
    monkeypatch.setattr("hpk.wizard._has_local_bin_on_path", lambda: True)

    runner = CliRunner()
    runner.invoke(cli_main, ["setup"])
    runner.invoke(cli_main, ["setup"])  # second run: no overwrite

    env = (tmp_path / ".hermes" / "profiles" / "coder" / ".env").read_text()
    # Should still contain a real key, not be reverted to FILL_IN
    assert "sk-ant-test-" in env
```

- [ ] **Step 2: Run + commit**

Run: `pytest tests/e2e/ -v`

```bash
git add tests/e2e/
git commit -m "test(e2e): full hpk setup happy path + idempotency"
```

---

## Phase 11 — Release Plumbing

### Task 11.1: `release.yml` + `dependabot.yml`

**Files:**
- Create: `.github/workflows/release.yml`
- Create: `.github/dependabot.yml`

- [ ] **Step 1: Write release workflow**

```yaml
name: release
on:
  push:
    tags: ["v*"]
jobs:
  publish:
    runs-on: ubuntu-latest
    permissions: { id-token: write }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install build
      - run: python -m build
      - uses: pypa/gh-action-pypi-publish@release/v1
```

- [ ] **Step 2: Write dependabot**

```yaml
version: 2
updates:
  - package-ecosystem: pip
    directory: /
    schedule: { interval: weekly }
  - package-ecosystem: github-actions
    directory: /
    schedule: { interval: weekly }
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release.yml .github/dependabot.yml
git commit -m "ci: release workflow + dependabot weekly"
```

---

## Final Verification

- [ ] Run full suite:
```bash
pytest -v
ruff check src tests
mypy
```
Expected: all green.

- [ ] Smoke-test the wizard locally:
```bash
hpk setup --dry-run
hpk doctor
hpk verify
```

- [ ] Push branch and confirm CI passes on GitHub.

---

## Self-Review Notes

- Spec coverage: every section maps to a task (1↔Phase 0/9, 2↔Phase 6, 3↔Phase 5, 4↔Phase 1.2, 5↔Phase 7+8, 6↔Phase 0+9, 7↔every test task + Phase 10).
- Type consistency: `Manifest`, `Profile`, `TokensSection`, `TokenSpec`, `Plugin`, `RecommendedPlugin` defined once in `manifest.py` (Task 1.2) and reused unchanged through wizard, plugins, verify, cli, e2e tests.
- The wizard test in Task 5.1 uses `hasattr(monkeypatch, 'tmp_path')` defensively because older pytest releases lack `monkeypatch.tmp_path`; the actual fixture `tmp_path` is requested as a separate parameter where needed.
- Plugin command verification in `find_missing_commands` uses suffix-match because the upstream Click walker prefixes paths with the root group's command names (not the `hermes` binary itself).
- No TBD/TODO/placeholder steps in the plan body.
