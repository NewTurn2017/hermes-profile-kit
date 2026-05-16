# 2-minute install Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship hermes-profile-kit 3.1.0 — `hpk setup` gains a non-interactive mode (`--token`, `--env-file`, `--accept-plugin`, `--reject-plugin`, `--non-interactive`) plus README/AGENTS.md fast-lane copy that an AI agent obeys, so an end user can install any kit profile via Claude Code in ≤ 2 minutes with one token round.

**Architecture:** Five focused changes layered low → high — new `src/hpk/env_file.py` module owns env-file parsing and key-level merge; `src/hpk/wizard.py` gains precedence logic and three typed errors; `src/hpk/cli.py` exposes the new flags and maps errors to exit 20/40; an E2E test proves the full seb path needs zero interactive reads; README/AGENTS.md/CHANGELOG/version bump close the marketing loop. No `manifest.yaml` schema changes; `TokenHandler.validate()` is already separate from prompting and is reused as-is.

**Tech Stack:** Python ≥ 3.10, Click, pydantic v2, pytest, ruff, mypy. Existing `tests/conftest.py::fake_hermes` fixture monkeypatches `subprocess.run` + `shutil.which`. `CliRunner` from `click.testing` drives CLI tests.

**Spec:** `docs/superpowers/specs/2026-05-16-fast-install-design.md`.

---

## File map (locked decisions)

- **Create** `src/hpk/env_file.py` — parse `KEY=VAL` files (comments + blanks OK), merge a `dict[str, str]` into an existing dotenv file at a given path while preserving sibling keys, write a sibling `.env.bak` snapshot before each write.
- **Modify** `src/hpk/wizard.py` — add `NonInteractiveMissingError`, `UnknownTokenKeyError`, `UnknownPluginIdError` (PreflightError subclasses), accept new args in `run_wizard` / `phase_b_tokens` / `phase_c_plugins`, implement value precedence and plugin overrides.
- **Modify** `src/hpk/cli.py` — register the five new options on `setup`, map the three new errors to exit codes 20 / 40 / 40.
- **Create** `tests/test_env_file.py` — unit tests for the new module.
- **Create** `tests/test_wizard_non_interactive.py` — tests the wizard's precedence + error paths directly (no CLI).
- **Modify** `tests/test_cli.py` — flag recognition + exit-code propagation through Click.
- **Create** `tests/e2e/test_non_interactive_setup.py` — full seb flow with zero `_prompt_secret` / `questionary.confirm` reads.
- **Modify** `README.md`, `README.ko.md` — `⚡ 2-minute install` hero above TL;DR table.
- **Modify** `AGENTS.md` — Standing user instructions + fast-path tables.
- **Modify** `CHANGELOG.md` — `## [3.1.0]` entry.
- **Modify** `pyproject.toml`, `src/hpk/__init__.py` — version 3.0.0 → 3.1.0.

---

## Task 1: `env_file` module — parse + key-level merge with `.env.bak`

**Files:**
- Create: `src/hpk/env_file.py`
- Create: `tests/test_env_file.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_env_file.py`:

```python
"""Unit tests for hpk.env_file — parse + key-level merge with .env.bak snapshot."""

from __future__ import annotations

from pathlib import Path

import pytest

from hpk.env_file import EnvFileParseError, load_env_file, merge_into_env


def test_load_env_file_parses_keys_and_skips_comments_blanks(tmp_path: Path) -> None:
    src = tmp_path / "tokens.env"
    src.write_text(
        "# comment\n"
        "\n"
        "SLACK_BOT_TOKEN=xoxb-abc\n"
        "  # leading spaces on comment\n"
        "SLACK_APP_TOKEN=xapp-xyz\n"
    )
    assert load_env_file(src) == {
        "SLACK_BOT_TOKEN": "xoxb-abc",
        "SLACK_APP_TOKEN": "xapp-xyz",
    }


def test_load_env_file_rejects_malformed_line(tmp_path: Path) -> None:
    src = tmp_path / "bad.env"
    src.write_text("not a key=val pair line\nSLACK_BOT_TOKEN=xoxb\n")
    with pytest.raises(EnvFileParseError, match="line 1"):
        load_env_file(src)


def test_load_env_file_rejects_lowercase_key(tmp_path: Path) -> None:
    src = tmp_path / "bad.env"
    src.write_text("slack_bot=xoxb\n")
    with pytest.raises(EnvFileParseError):
        load_env_file(src)


def test_merge_into_env_updates_only_named_keys_and_preserves_siblings(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "SLACK_BOT_TOKEN=old\n"
        "UNRELATED_KEY=keep_me\n"
        "SLACK_APP_TOKEN=FILL_IN\n"
    )
    merge_into_env(env, {"SLACK_BOT_TOKEN": "xoxb-new", "SLACK_APP_TOKEN": "xapp-new"})
    text = env.read_text()
    assert "SLACK_BOT_TOKEN=xoxb-new" in text
    assert "SLACK_APP_TOKEN=xapp-new" in text
    assert "UNRELATED_KEY=keep_me" in text
    assert "old" not in text


def test_merge_into_env_writes_dot_env_bak_with_prior_contents(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("SLACK_BOT_TOKEN=old\n")
    merge_into_env(env, {"SLACK_BOT_TOKEN": "xoxb-new"})
    bak = tmp_path / ".env.bak"
    assert bak.exists()
    assert bak.read_text() == "SLACK_BOT_TOKEN=old\n"


def test_merge_into_env_overwrites_existing_dot_env_bak_on_rerun(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("SLACK_BOT_TOKEN=v1\n")
    merge_into_env(env, {"SLACK_BOT_TOKEN": "v2"})
    merge_into_env(env, {"SLACK_BOT_TOKEN": "v3"})
    assert (tmp_path / ".env.bak").read_text() == "SLACK_BOT_TOKEN=v2\n"
    assert (tmp_path / ".env").read_text().strip() == "SLACK_BOT_TOKEN=v3"


def test_merge_into_env_creates_missing_env_with_0600(tmp_path: Path) -> None:
    env = tmp_path / "subdir" / ".env"
    merge_into_env(env, {"SLACK_BOT_TOKEN": "xoxb-new"})
    assert env.read_text() == "SLACK_BOT_TOKEN=xoxb-new\n"
    assert oct(env.stat().st_mode & 0o777) == "0o600"
    # No backup for an absent prior file.
    assert not (tmp_path / "subdir" / ".env.bak").exists()


def test_merge_into_env_appends_new_keys_when_absent(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("EXISTING=1\n")
    merge_into_env(env, {"NEW_KEY": "v"})
    text = env.read_text()
    assert "EXISTING=1" in text
    assert "NEW_KEY=v" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_env_file.py -v`
Expected: ALL fail with `ModuleNotFoundError: No module named 'hpk.env_file'`.

- [ ] **Step 3: Implement the module**

Create `src/hpk/env_file.py`:

```python
"""`KEY=VAL` file parser + key-level merge into an existing dotenv with `.env.bak` snapshot."""

from __future__ import annotations

import re
from pathlib import Path

from hpk.profiles import atomic_write, set_env_key


class EnvFileParseError(ValueError):
    """Raised when --env-file content cannot be parsed."""


_ENV_LINE = re.compile(r"^(?P<key>[A-Z_][A-Z0-9_]*)=(?P<val>.*)$")


def load_env_file(path: Path) -> dict[str, str]:
    """Parse a KEY=VAL file. `#` line comments and blank lines are allowed.

    Keys must match `[A-Z_][A-Z0-9_]*` (matches the dotenv convention used by
    `hpk.profiles.set_env_key`). Raises EnvFileParseError on the first
    malformed line, including the 1-based line number.
    """
    out: dict[str, str] = {}
    for i, raw in enumerate(path.read_text().splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _ENV_LINE.match(line)
        if not m:
            raise EnvFileParseError(f"{path}: line {i}: malformed env line: {raw!r}")
        out[m.group("key")] = m.group("val")
    return out


def merge_into_env(target: Path, values: dict[str, str]) -> None:
    """Update `target` so each KEY in `values` maps to its VAL. Other lines untouched.

    If `target` exists and contains content, write a snapshot to `target` + `.bak`
    *before* mutating, overwriting any previous backup. If `target` does not
    exist, create it (mode 0600) and skip the backup.
    """
    if target.exists():
        prior = target.read_text()
        atomic_write(target.with_suffix(target.suffix + ".bak"), prior, mode=0o600)
    for key, val in values.items():
        set_env_key(target, key, val)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_env_file.py -v`
Expected: 7 passed.

- [ ] **Step 5: Lint + type-check**

Run: `ruff check src/hpk/env_file.py tests/test_env_file.py && ruff format --check src/hpk/env_file.py tests/test_env_file.py && mypy src/hpk`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/hpk/env_file.py tests/test_env_file.py
git commit -m "$(cat <<'EOF'
feat(env): key-level env_file helper with .env.bak safety net

Parse KEY=VAL files (comments + blanks allowed). Merge into an existing
.env preserving sibling keys; snapshot the prior file to .env.bak before
writing. Mode 0600 throughout.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Wizard — precedence, plugin overrides, typed errors

**Files:**
- Modify: `src/hpk/wizard.py`
- Create: `tests/test_wizard_non_interactive.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_wizard_non_interactive.py`:

```python
"""phase_b_tokens / phase_c_plugins under non-interactive mode + overrides."""

from __future__ import annotations

from pathlib import Path

import pytest

from hpk import wizard
from hpk.manifest import Plugin, Profile, RecommendedPlugin, TokenSpec, TokensSection
from hpk.wizard import (
    NonInteractiveMissingError,
    UnknownPluginIdError,
    UnknownTokenKeyError,
    phase_b_tokens,
    phase_c_plugins,
)


def _seb_profile() -> Profile:
    return Profile(
        name="seb",
        template="profiles/seb",
        role="second brain",
        model_tier="openai-codex",
        channels=["slack"],
        tokens=TokensSection(
            required=[
                TokenSpec(key="SLACK_BOT_TOKEN", provider="slack", wizard="slack_bot"),
                TokenSpec(key="SLACK_SIGNING_SECRET", provider="slack", wizard="slack_signing"),
                TokenSpec(key="SLACK_APP_TOKEN", provider="slack", wizard="slack_app"),
                TokenSpec(
                    key="OPENAI_BASE_URL",
                    provider="openai-codex",
                    wizard="codex_base_url",
                    default="http://localhost:8765/v1",
                ),
            ],
            optional=[],
        ),
        recommended_plugins=[RecommendedPlugin(id="codex-openai-proxy", default=True)],
    )


_BOT = "xoxb-" + "0" * 30
_SIGN = "a" * 32
_APP = "xapp-" + "0" * 30


def test_phase_b_with_all_tokens_via_flags_writes_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = _seb_profile()
    phase_b_tokens(
        p,
        non_interactive=True,
        token_overrides={
            "SLACK_BOT_TOKEN": _BOT,
            "SLACK_SIGNING_SECRET": _SIGN,
            "SLACK_APP_TOKEN": _APP,
        },
        env_file_values={},
    )
    env = (tmp_path / ".hermes" / "profiles" / "seb" / ".env").read_text()
    assert f"SLACK_BOT_TOKEN={_BOT}" in env
    assert f"SLACK_SIGNING_SECRET={_SIGN}" in env
    assert f"SLACK_APP_TOKEN={_APP}" in env
    # Default-bearing token uses its manifest default under non-interactive.
    assert "OPENAI_BASE_URL=http://localhost:8765/v1" in env


def test_phase_b_snapshots_existing_env_to_bak_when_flags_used(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    home = tmp_path / ".hermes" / "profiles" / "seb"
    home.mkdir(parents=True)
    (home / ".env").write_text("SLACK_BOT_TOKEN=old-value\nUNRELATED=keep\n")
    p = _seb_profile()
    phase_b_tokens(
        p,
        non_interactive=True,
        token_overrides={
            "SLACK_BOT_TOKEN": _BOT,
            "SLACK_SIGNING_SECRET": _SIGN,
            "SLACK_APP_TOKEN": _APP,
        },
        env_file_values={},
    )
    bak = (home / ".env.bak").read_text()
    assert "SLACK_BOT_TOKEN=old-value" in bak
    assert "UNRELATED=keep" in bak
    env = (home / ".env").read_text()
    assert f"SLACK_BOT_TOKEN={_BOT}" in env
    assert "UNRELATED=keep" in env
    assert "old-value" not in env


def test_phase_b_non_interactive_missing_required_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = _seb_profile()
    with pytest.raises(NonInteractiveMissingError) as exc:
        phase_b_tokens(
            p,
            non_interactive=True,
            token_overrides={"SLACK_BOT_TOKEN": _BOT},  # 2 required still missing
            env_file_values={},
        )
    msg = str(exc.value)
    assert "SLACK_SIGNING_SECRET" in msg
    assert "SLACK_APP_TOKEN" in msg


def test_phase_b_token_flag_beats_env_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = _seb_profile()
    phase_b_tokens(
        p,
        non_interactive=True,
        token_overrides={"SLACK_BOT_TOKEN": _BOT},
        env_file_values={
            "SLACK_BOT_TOKEN": "xoxb-fromfile",
            "SLACK_SIGNING_SECRET": _SIGN,
            "SLACK_APP_TOKEN": _APP,
        },
    )
    env = (tmp_path / ".hermes" / "profiles" / "seb" / ".env").read_text()
    assert f"SLACK_BOT_TOKEN={_BOT}" in env
    assert "xoxb-fromfile" not in env


def test_phase_b_validation_failure_via_flag_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = _seb_profile()
    with pytest.raises(NonInteractiveMissingError, match="SLACK_BOT_TOKEN"):
        phase_b_tokens(
            p,
            non_interactive=True,
            token_overrides={
                "SLACK_BOT_TOKEN": "not-xoxb-prefixed",
                "SLACK_SIGNING_SECRET": _SIGN,
                "SLACK_APP_TOKEN": _APP,
            },
            env_file_values={},
        )


def test_phase_b_unknown_token_key_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = _seb_profile()
    with pytest.raises(UnknownTokenKeyError, match="NOT_A_KEY"):
        phase_b_tokens(
            p,
            non_interactive=True,
            token_overrides={"NOT_A_KEY": "x"},
            env_file_values={},
        )


def _make_catalog() -> dict[str, Plugin]:
    return {
        "codex-openai-proxy": Plugin(
            description="local proxy",
            upstream_command=None,
            install_path="scripts/codex-openai-proxy",
            launchd_template=None,
            verified_in_upstream=False,
            docs=None,
        ),
    }


def test_phase_c_accept_flag_overrides_default_false(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = _seb_profile()
    p.recommended_plugins = [RecommendedPlugin(id="codex-openai-proxy", default=False)]
    asked: list[str] = []
    monkeypatch.setattr(wizard, "_ask_plugin", lambda pid, default: asked.append(pid) or True)
    phase_c_plugins(
        p,
        _make_catalog(),
        non_interactive=True,
        accepted_plugins={"codex-openai-proxy"},
        rejected_plugins=set(),
    )
    assert asked == []  # never prompted in non-interactive


def test_phase_c_reject_beats_accept_on_same_id(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = _seb_profile()
    phase_c_plugins(
        p,
        _make_catalog(),
        non_interactive=True,
        accepted_plugins={"codex-openai-proxy"},
        rejected_plugins={"codex-openai-proxy"},
    )
    captured = capsys.readouterr().out
    assert "codex-openai-proxy" in captured
    assert "skipped" in captured.lower() or "reject" in captured.lower()


def test_phase_c_unknown_plugin_id_in_flags_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = _seb_profile()
    with pytest.raises(UnknownPluginIdError, match="not-a-plugin"):
        phase_c_plugins(
            p,
            _make_catalog(),
            non_interactive=True,
            accepted_plugins={"not-a-plugin"},
            rejected_plugins=set(),
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_wizard_non_interactive.py -v`
Expected: ALL fail (`ImportError: cannot import name 'NonInteractiveMissingError'` etc.).

- [ ] **Step 3: Add the typed errors + helper**

Edit `src/hpk/wizard.py` — add these classes immediately below `HermesVersionTooOldError`:

```python
class NonInteractiveMissingError(PreflightError):
    """Required token value missing or invalid under --non-interactive."""

    def __init__(self, missing: list[str], invalid: list[tuple[str, str]] | None = None) -> None:
        invalid = invalid or []
        parts: list[str] = []
        if missing:
            parts.append("missing required tokens: " + ", ".join(missing))
        if invalid:
            parts.append(
                "invalid token values: " + ", ".join(f"{k} ({why})" for k, why in invalid)
            )
        super().__init__(
            "; ".join(parts)
            + ". Re-run with --token KEY=VAL for each missing/invalid key."
        )


class UnknownTokenKeyError(PreflightError):
    """`--token KEY=VAL` named a key the target profile does not declare."""


class UnknownPluginIdError(PreflightError):
    """`--accept-plugin`/`--reject-plugin` named an id not in recommended_plugins."""
```

- [ ] **Step 4: Refactor `phase_b_tokens` to accept overrides + precedence**

Replace the existing `phase_b_tokens` in `src/hpk/wizard.py` with:

```python
def phase_b_tokens(
    profile: Profile,
    *,
    non_interactive: bool = False,
    token_overrides: dict[str, str] | None = None,
    env_file_values: dict[str, str] | None = None,
) -> None:
    ui.step(f"[B] tokens — {profile.name}")
    overrides = dict(token_overrides or {})
    env_values = dict(env_file_values or {})

    known_keys = {s.key for s in profile.tokens.required} | {s.key for s in profile.tokens.optional}
    for src_name, src in (("--token", overrides), ("--env-file", env_values)):
        unknown = sorted(set(src) - known_keys)
        if unknown:
            raise UnknownTokenKeyError(
                f"{src_name}: unknown key(s) for profile {profile.name!r}: {', '.join(unknown)}. "
                f"Valid: {', '.join(sorted(known_keys))}"
            )

    home = profiles.profile_home(profile.name)
    env_path = home / ".env"

    # Safety snapshot: if flags are about to mutate an existing .env, copy it to .env.bak first.
    # Interactive runs keep their current behavior (no snapshot).
    if env_path.exists() and (overrides or env_values):
        profiles.atomic_write(
            env_path.with_suffix(env_path.suffix + ".bak"),
            env_path.read_text(),
            mode=0o600,
        )

    missing: list[str] = []
    invalid: list[tuple[str, str]] = []

    for spec in profile.tokens.required:
        val = _resolve_value(spec, overrides=overrides, env_values=env_values)
        if val is not None:
            handler = _handler_for(spec)
            r = handler.validate(val)
            if not r.ok:
                invalid.append((spec.key, r.reason))
                continue
            profiles.set_env_key(env_path, spec.key, val)
            ui.ok(f"{spec.key} written")
            continue
        if non_interactive:
            if spec.default is not None:
                profiles.set_env_key(env_path, spec.key, spec.default)
                ui.ok(f"{spec.key} written (manifest default)")
            else:
                missing.append(spec.key)
            continue
        # interactive fallback (existing behavior)
        v = _collect_one(spec, optional=False)
        if v:
            profiles.set_env_key(env_path, spec.key, v)
            ui.ok(f"{spec.key} written")
        else:
            ui.warn(f"{spec.key} left as FILL_IN")

    if non_interactive and (missing or invalid):
        raise NonInteractiveMissingError(missing=missing, invalid=invalid)

    for spec in profile.tokens.optional:
        val = _resolve_value(spec, overrides=overrides, env_values=env_values)
        if val is not None:
            handler = _handler_for(spec)
            r = handler.validate(val)
            if not r.ok:
                if non_interactive:
                    invalid.append((spec.key, r.reason))
                else:
                    ui.warn(f"{spec.key} invalid ({r.reason}) — left as-is")
                continue
            profiles.set_env_key(env_path, spec.key, val)
            ui.ok(f"{spec.key} written")
            continue
        if non_interactive:
            continue  # leave FILL_IN, no error for optional
        v = _collect_one(spec, optional=True)
        if v:
            profiles.set_env_key(env_path, spec.key, v)
            ui.ok(f"{spec.key} written")

    if non_interactive and invalid:
        raise NonInteractiveMissingError(missing=[], invalid=invalid)


def _resolve_value(
    spec: TokenSpec,
    *,
    overrides: dict[str, str],
    env_values: dict[str, str],
) -> str | None:
    """Precedence: --token (highest) > --env-file > manifest default > None."""
    if spec.key in overrides:
        return overrides[spec.key]
    if spec.key in env_values:
        return env_values[spec.key]
    return None  # manifest default is applied later only under non-interactive


def _handler_for(spec: TokenSpec):  # type: ignore[no-untyped-def]
    return (
        tokens.get_handler(provider=spec.provider, wizard=spec.wizard)
        if spec.wizard
        else tokens.get_handler(provider=spec.provider)
    )
```

- [ ] **Step 5: Refactor `phase_c_plugins` to accept override sets**

Replace the existing `phase_c_plugins` in `src/hpk/wizard.py` with:

```python
def phase_c_plugins(
    profile: Profile,
    plugins_catalog: dict[str, Plugin],
    *,
    non_interactive: bool = False,
    accepted_plugins: set[str] | None = None,
    rejected_plugins: set[str] | None = None,
) -> None:
    accepted = set(accepted_plugins or ())
    rejected = set(rejected_plugins or ())

    known_ids = {rp.id for rp in profile.recommended_plugins}
    unknown_flagged = sorted((accepted | rejected) - known_ids)
    if unknown_flagged:
        raise UnknownPluginIdError(
            f"unknown plugin id(s) for profile {profile.name!r}: {', '.join(unknown_flagged)}. "
            f"Valid: {', '.join(sorted(known_ids)) or '(none)'}"
        )

    conflicts = accepted & rejected
    for pid in sorted(conflicts):
        ui.warn(f"plugin {pid}: both --accept-plugin and --reject-plugin given; reject wins")

    if not profile.recommended_plugins:
        return
    ui.step(f"[C] plugins — {profile.name}")
    for rp in profile.recommended_plugins:
        plugin = plugins_catalog.get(rp.id)
        if plugin is None:
            ui.warn(f"plugin {rp.id} not found in catalog — skipping")
            continue

        decision = _decide_plugin(
            rp_id=rp.id,
            default=rp.default,
            accepted=accepted,
            rejected=rejected,
            non_interactive=non_interactive,
        )
        if not decision:
            ui.ok(f"plugin {rp.id} skipped")
            continue

        # Kit-local helper: print install path, never exec hermes.
        if plugin.install_path and not plugin.verified_in_upstream:
            ui.warn(
                f"plugin [bold]{rp.id}[/bold] is a kit-local helper. "
                f"Install manually: see [cyan]{plugin.install_path}/README.md[/cyan]"
            )
            if plugin.launchd_template:
                ui.console.print(f"  launchd template: {plugin.launchd_template}")
            continue

        if not plugin.verified_in_upstream:
            ui.warn(f"plugin {rp.id} not verified — skipping")
            continue
        try:
            plugins_mod.run_plugin(plugin, profile=profile.name)
            ui.ok(f"plugin {rp.id} enabled")
        except plugins_mod.PluginExecError as e:
            ui.warn(f"plugin {rp.id} failed: {e}")


def _decide_plugin(
    *,
    rp_id: str,
    default: bool,
    accepted: set[str],
    rejected: set[str],
    non_interactive: bool,
) -> bool:
    if rp_id in rejected:
        return False
    if rp_id in accepted:
        return True
    if non_interactive:
        return default
    return _ask_plugin(rp_id, default)
```

- [ ] **Step 6: Extend `run_wizard` to thread the new args**

In `src/hpk/wizard.py`, replace the existing `run_wizard` with:

```python
def run_wizard(
    manifest: Manifest,
    *,
    targets: list[str],
    force: bool,
    skip_tokens: bool,
    skip_plugins: bool,
    non_interactive: bool = False,
    token_overrides: dict[str, str] | None = None,
    env_file_values: dict[str, str] | None = None,
    accepted_plugins: set[str] | None = None,
    rejected_plugins: set[str] | None = None,
) -> None:
    preflight(manifest)
    selected = [p for p in manifest.profiles if not targets or p.name in targets]
    for profile in selected:
        ui.header(f"profile {profile.name}")
        phase_a_base(profile, force=force)
        if not skip_tokens:
            phase_b_tokens(
                profile,
                non_interactive=non_interactive,
                token_overrides=token_overrides,
                env_file_values=env_file_values,
            )
        if not skip_plugins:
            phase_c_plugins(
                profile,
                manifest.plugins,
                non_interactive=non_interactive,
                accepted_plugins=accepted_plugins,
                rejected_plugins=rejected_plugins,
            )
```

- [ ] **Step 7: Run the new tests**

Run: `pytest tests/test_wizard_non_interactive.py -v`
Expected: 9 passed.

- [ ] **Step 8: Run the full suite to confirm no regressions**

Run: `pytest -q`
Expected: all green. Prior baseline was 88; with Task 1's 7 + this task's 9, expect ~104 total.

- [ ] **Step 9: Lint + type-check**

Run: `ruff check src/hpk tests && ruff format --check src/hpk tests && mypy src/hpk`
Expected: clean.

- [ ] **Step 10: Commit**

```bash
git add src/hpk/wizard.py tests/test_wizard_non_interactive.py
git commit -m "$(cat <<'EOF'
feat(wizard): non-interactive precedence + plugin overrides + typed errors

phase_b_tokens accepts token_overrides + env_file_values and resolves
values in --token > --env-file > manifest default order. Under
non_interactive, missing required tokens raise NonInteractiveMissingError;
unknown KEYs raise UnknownTokenKeyError. phase_c_plugins accepts
accepted_plugins / rejected_plugins sets; reject wins on conflict;
unknown plugin ids raise UnknownPluginIdError.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: CLI — wire the five flags, map errors to exit codes

**Files:**
- Modify: `src/hpk/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing CLI tests**

Append to `tests/test_cli.py`:

```python
MANIFEST_YAML_SEB_MIN = """schema_version: 3
kit: {name: hpk, version: 3.0.0, license: MIT}
upstream: {repo: x, pinned_commit: c, pinned_version: 0.12.3, verified_at: t}
min_hermes_version: 0.12.0
profiles:
  - name: seb
    template: profiles/seb
    role: second brain
    model_tier: openai-codex
    channels: [slack]
    tokens:
      required:
        - { key: SLACK_BOT_TOKEN, provider: slack, wizard: slack_bot }
      optional: []
    recommended_plugins:
      - { id: codex-openai-proxy, default: true }
plugins:
  codex-openai-proxy:
    description: local
    upstream_command: null
    install_path: scripts/codex-openai-proxy
    verified_in_upstream: false
"""


def _scaffold_seb_min(tmp_path) -> None:
    (tmp_path / "manifest.yaml").write_text(MANIFEST_YAML_SEB_MIN)
    tpl = tmp_path / "profiles" / "seb"
    tpl.mkdir(parents=True)
    (tpl / "SOUL.md").write_text("soul")
    (tpl / "config.yaml").write_text("model:\n  default: openai/gpt-5.5\n")
    (tpl / ".env.example").write_text("SLACK_BOT_TOKEN=FILL_IN\n")


def test_setup_help_lists_non_interactive_flags() -> None:
    r = CliRunner().invoke(main, ["setup", "--help"])
    assert r.exit_code == 0
    for flag in ("--token", "--env-file", "--accept-plugin", "--reject-plugin", "--non-interactive"):
        assert flag in r.output


def test_setup_non_interactive_missing_required_exits_20(fake_hermes, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _scaffold_seb_min(tmp_path)
    monkeypatch.setattr("hpk.wizard._has_local_bin_on_path", lambda: True)
    r = CliRunner().invoke(main, ["setup", "seb", "--non-interactive"])
    assert r.exit_code == 20, r.output
    assert "SLACK_BOT_TOKEN" in r.output


def test_setup_non_interactive_unknown_token_exits_40(fake_hermes, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _scaffold_seb_min(tmp_path)
    monkeypatch.setattr("hpk.wizard._has_local_bin_on_path", lambda: True)
    r = CliRunner().invoke(
        main,
        ["setup", "seb", "--non-interactive", "--token", "NOT_A_KEY=x", "--token",
         "SLACK_BOT_TOKEN=xoxb-" + "0" * 30],
    )
    assert r.exit_code == 40, r.output
    assert "NOT_A_KEY" in r.output


def test_setup_non_interactive_unknown_plugin_exits_40(fake_hermes, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _scaffold_seb_min(tmp_path)
    monkeypatch.setattr("hpk.wizard._has_local_bin_on_path", lambda: True)
    r = CliRunner().invoke(
        main,
        [
            "setup", "seb", "--non-interactive",
            "--token", "SLACK_BOT_TOKEN=xoxb-" + "0" * 30,
            "--accept-plugin", "ghost-plugin",
        ],
    )
    assert r.exit_code == 40, r.output
    assert "ghost-plugin" in r.output


def test_setup_env_file_loaded_and_token_flag_wins(fake_hermes, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _scaffold_seb_min(tmp_path)
    monkeypatch.setattr("hpk.wizard._has_local_bin_on_path", lambda: True)
    bot_from_file = "xoxb-" + "f" * 30
    bot_from_flag = "xoxb-" + "9" * 30
    (tmp_path / "tokens.env").write_text(f"SLACK_BOT_TOKEN={bot_from_file}\n")
    r = CliRunner().invoke(
        main,
        [
            "setup", "seb", "--non-interactive",
            "--env-file", str(tmp_path / "tokens.env"),
            "--token", f"SLACK_BOT_TOKEN={bot_from_flag}",
        ],
    )
    assert r.exit_code == 0, r.output
    env = (tmp_path / ".hermes" / "profiles" / "seb" / ".env").read_text()
    assert bot_from_flag in env
    assert bot_from_file not in env
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v -k "non_interactive or env_file or non_interactive_flags"`
Expected: 5 tests fail (`Error: No such option: --non-interactive` for the first ones).

- [ ] **Step 3: Implement the CLI flags + exit mapping**

Replace the `setup` command in `src/hpk/cli.py` with:

```python
@main.command()
@click.argument("profile", nargs=-1)
@click.option("--force", is_flag=True, help="Overwrite SOUL.md/config.yaml even if present.")
@click.option("--skip-tokens", is_flag=True)
@click.option("--skip-plugins", is_flag=True)
@click.option(
    "--token",
    "tokens_kv",
    multiple=True,
    metavar="KEY=VAL",
    help="Inject a token value without prompting. Repeatable.",
)
@click.option(
    "--env-file",
    "env_file_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Load KEY=VAL lines (# comments allowed). --token values take precedence.",
)
@click.option(
    "--accept-plugin",
    "accept_plugins",
    multiple=True,
    metavar="ID",
    help="Force-enable a recommended plugin. Repeatable.",
)
@click.option(
    "--reject-plugin",
    "reject_plugins",
    multiple=True,
    metavar="ID",
    help="Force-skip a recommended plugin. Repeatable. Beats --accept-plugin on conflict.",
)
@click.option(
    "--non-interactive",
    is_flag=True,
    help="Fail with exit 20 instead of prompting when a required value is missing.",
)
def setup(
    profile: tuple[str, ...],
    force: bool,
    skip_tokens: bool,
    skip_plugins: bool,
    tokens_kv: tuple[str, ...],
    env_file_path: Path | None,
    accept_plugins: tuple[str, ...],
    reject_plugins: tuple[str, ...],
    non_interactive: bool,
) -> None:
    """Interactive multi-profile setup. See README's '2-minute install' for non-interactive use."""
    manifest = _load()

    token_overrides: dict[str, str] = {}
    for kv in tokens_kv:
        if "=" not in kv:
            ui.err(f"--token expects KEY=VAL, got: {kv!r}")
            sys.exit(40)
        key, _, val = kv.partition("=")
        token_overrides[key] = val

    env_file_values: dict[str, str] = {}
    if env_file_path is not None:
        from hpk.env_file import EnvFileParseError, load_env_file

        try:
            env_file_values = load_env_file(env_file_path)
        except EnvFileParseError as e:
            ui.err(str(e))
            sys.exit(40)

    try:
        wizard.run_wizard(
            manifest,
            targets=list(profile),
            force=force,
            skip_tokens=skip_tokens,
            skip_plugins=skip_plugins,
            non_interactive=non_interactive,
            token_overrides=token_overrides,
            env_file_values=env_file_values,
            accepted_plugins=set(accept_plugins),
            rejected_plugins=set(reject_plugins),
        )
    except wizard.HermesNotInstalledError as e:
        ui.err(str(e))
        sys.exit(10)
    except wizard.HermesVersionTooOldError as e:
        ui.err(str(e))
        sys.exit(11)
    except wizard.NonInteractiveMissingError as e:
        ui.err(str(e))
        sys.exit(20)
    except (wizard.UnknownTokenKeyError, wizard.UnknownPluginIdError) as e:
        ui.err(str(e))
        sys.exit(40)
    except wizard.PreflightError as e:
        ui.err(str(e))
        sys.exit(30)
```

- [ ] **Step 4: Run the CLI tests**

Run: `pytest tests/test_cli.py -v`
Expected: all green (old + 5 new = whatever total).

- [ ] **Step 5: Full suite**

Run: `pytest -q`
Expected: all green.

- [ ] **Step 6: Lint + type-check**

Run: `ruff check src/hpk tests && ruff format --check src/hpk tests && mypy src/hpk`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add src/hpk/cli.py tests/test_cli.py
git commit -m "$(cat <<'EOF'
feat(cli): wire --token/--env-file/--accept-plugin/--reject-plugin/--non-interactive

Map NonInteractiveMissingError → exit 20, UnknownTokenKey / UnknownPluginId
→ exit 40. --token parses KEY=VAL with explicit error on missing '='.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: E2E — non-interactive seb setup proves zero interactive reads

**Files:**
- Create: `tests/e2e/test_non_interactive_setup.py`

- [ ] **Step 1: Write the test**

Create `tests/e2e/test_non_interactive_setup.py`:

```python
# ruff: noqa: E501  # YAML fixture preserves manifest layout for readability.
"""E2E: hpk setup seb --non-interactive completes without any interactive read."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from hpk.cli import main as cli_main

_MANIFEST_YAML = """\
schema_version: 3
kit: {name: hpk, version: 3.0.0, license: MIT}
upstream: {repo: x, pinned_commit: abc, pinned_version: 0.12.3, verified_at: 2026-05-15T09:49Z}
min_hermes_version: 0.12.0
profiles:
  - name: seb
    template: profiles/seb
    role: second brain
    model_tier: openai-codex
    channels: [slack]
    tokens:
      required:
        - { key: SLACK_BOT_TOKEN,      provider: slack,        wizard: slack_bot     }
        - { key: SLACK_SIGNING_SECRET, provider: slack,        wizard: slack_signing }
        - { key: SLACK_APP_TOKEN,      provider: slack,        wizard: slack_app     }
        - { key: OPENAI_BASE_URL,      provider: openai-codex, wizard: codex_base_url, default: "http://localhost:8765/v1" }
        - { key: OPENAI_API_KEY,       provider: openai-codex, wizard: codex_api_key,  default: "sk-codex-proxy-local" }
      optional: []
    recommended_plugins:
      - { id: codex-openai-proxy, default: true }
plugins:
  codex-openai-proxy:
    description: local proxy
    upstream_command: null
    install_path: scripts/codex-openai-proxy
    launchd_template: scripts/codex-openai-proxy/launchd.plist.example
    verified_in_upstream: false
    docs: scripts/codex-openai-proxy/README.md
preserve_existing: [.env]
overwrite_from_template: [SOUL.md, config.yaml]
"""

_BOT = "xoxb-" + "0" * 30
_SIGN = "a" * 32
_APP = "xapp-" + "0" * 30


def _scaffold(tmp_path: Path) -> None:
    (tmp_path / "manifest.yaml").write_text(_MANIFEST_YAML)
    tpl = tmp_path / "profiles" / "seb"
    tpl.mkdir(parents=True)
    (tpl / "SOUL.md").write_text("soul")
    (tpl / "config.yaml").write_text("model:\n  default: openai/gpt-5.5\n")
    (tpl / ".env.example").write_text(
        "SLACK_BOT_TOKEN=FILL_IN\n"
        "SLACK_SIGNING_SECRET=FILL_IN\n"
        "SLACK_APP_TOKEN=FILL_IN\n"
        "OPENAI_BASE_URL=http://localhost:8765/v1\n"
        "OPENAI_API_KEY=sk-codex-proxy-local\n"
    )
    (tmp_path / "scripts" / "codex-openai-proxy").mkdir(parents=True)


def test_e2e_seb_non_interactive_completes_with_zero_interactive_reads(
    fake_hermes, tmp_path, monkeypatch
):
    _scaffold(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("hpk.wizard._has_local_bin_on_path", lambda: True)

    # Boobytrap every interactive entry point — touching any of these is the failure mode
    # this test is meant to catch.
    def _explode(*a, **kw):
        raise AssertionError("interactive prompt called during --non-interactive run")

    from hpk import wizard

    monkeypatch.setattr(wizard, "_prompt_secret", _explode)
    monkeypatch.setattr(wizard, "_ask_plugin", _explode)
    monkeypatch.setattr("questionary.password", _explode)
    monkeypatch.setattr("questionary.confirm", _explode)

    r = CliRunner().invoke(
        cli_main,
        [
            "setup", "seb", "--non-interactive",
            "--token", f"SLACK_BOT_TOKEN={_BOT}",
            "--token", f"SLACK_SIGNING_SECRET={_SIGN}",
            "--token", f"SLACK_APP_TOKEN={_APP}",
            "--accept-plugin", "codex-openai-proxy",
        ],
    )
    assert r.exit_code == 0, r.output

    env = (tmp_path / ".hermes" / "profiles" / "seb" / ".env").read_text()
    assert f"SLACK_BOT_TOKEN={_BOT}" in env
    assert f"SLACK_SIGNING_SECRET={_SIGN}" in env
    assert f"SLACK_APP_TOKEN={_APP}" in env
    assert "OPENAI_BASE_URL=http://localhost:8765/v1" in env
    assert "OPENAI_API_KEY=sk-codex-proxy-local" in env

    # hermes was called to create the profile, NOT to install the kit-local proxy.
    assert ["hermes", "profile", "create", "seb"] in fake_hermes.calls
    assert "codex-openai-proxy" not in str(fake_hermes.calls)


def test_e2e_seb_non_interactive_env_file_alone_suffices(
    fake_hermes, tmp_path, monkeypatch
):
    _scaffold(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("hpk.wizard._has_local_bin_on_path", lambda: True)

    def _explode(*a, **kw):
        raise AssertionError("interactive prompt called during --non-interactive run")

    from hpk import wizard

    monkeypatch.setattr(wizard, "_prompt_secret", _explode)
    monkeypatch.setattr(wizard, "_ask_plugin", _explode)
    monkeypatch.setattr("questionary.password", _explode)
    monkeypatch.setattr("questionary.confirm", _explode)

    (tmp_path / "tokens.env").write_text(
        "# slack creds for this workspace\n"
        f"SLACK_BOT_TOKEN={_BOT}\n"
        f"SLACK_SIGNING_SECRET={_SIGN}\n"
        f"SLACK_APP_TOKEN={_APP}\n"
    )

    r = CliRunner().invoke(
        cli_main,
        [
            "setup", "seb", "--non-interactive",
            "--env-file", str(tmp_path / "tokens.env"),
            "--accept-plugin", "codex-openai-proxy",
        ],
    )
    assert r.exit_code == 0, r.output
    env = (tmp_path / ".hermes" / "profiles" / "seb" / ".env").read_text()
    assert f"SLACK_BOT_TOKEN={_BOT}" in env
    assert "OPENAI_BASE_URL=http://localhost:8765/v1" in env  # manifest default applied
```

- [ ] **Step 2: Run the new E2E tests**

Run: `pytest tests/e2e/test_non_interactive_setup.py -v`
Expected: 2 passed.

- [ ] **Step 3: Run the full suite**

Run: `pytest -q`
Expected: all green.

- [ ] **Step 4: Lint + type-check**

Run: `ruff check tests/e2e/test_non_interactive_setup.py && ruff format --check tests/e2e/test_non_interactive_setup.py && mypy src/hpk`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/test_non_interactive_setup.py
git commit -m "$(cat <<'EOF'
test(e2e): non-interactive seb setup completes with zero interactive reads

Boobytraps _prompt_secret, _ask_plugin, questionary.password,
questionary.confirm — touching any of them fails the test. Proves the
'2-minute install' claim is enforceable.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Docs (README + AGENTS) + CHANGELOG + version bump to 3.1.0

**Files:**
- Modify: `README.md`
- Modify: `README.ko.md`
- Modify: `AGENTS.md`
- Modify: `CHANGELOG.md`
- Modify: `pyproject.toml`
- Modify: `src/hpk/__init__.py`

- [ ] **Step 1: Add the `⚡ 2-minute install` hero to `README.md`**

Insert this block immediately *above* the line `## TL;DR — 어디서부터 읽어야 하나 / Where to start`:

```markdown
## ⚡ 2-minute install (Claude Code / Codex)

Paste into Claude Code or `codex`. One token round, done.

> Install the Hermes **`<PROFILE>`** profile on this machine using
> `hermes-profile-kit`. This is a deterministic CLI install, not a
> software-design task. Do not invoke `brainstorming`, `writing-plans`,
> `test-driven-development`, or `requesting-code-review` skills — the
> user has explicitly instructed you not to. Ask me for any required
> tokens in a single message, then run:
>
>     pipx install --upgrade hermes-profile-kit
>     hpk setup <PROFILE> --non-interactive \
>       --token KEY1=<v1> --token KEY2=<v2> ... \
>       --accept-plugin <plugin-id>
>     hpk verify <PROFILE>
>
> Required tokens & plugin ids are in
> https://github.com/NewTurn2017/hermes-profile-kit/blob/main/manifest.yaml.
> Report the verify output when done.

**Live example — `seb` (Slack second-brain via Codex):** see [AGENTS.md → seb fast-path](AGENTS.md#fast-path-seb).

```

- [ ] **Step 2: Add the same hero (Korean) to `README.ko.md`**

Insert immediately *above* the line `## TL;DR — 어디서부터 읽어야 하나` (line 11 in the current file):

```markdown
## ⚡ 2분 설치 (Claude Code / Codex)

Claude Code 또는 `codex`에 그대로 붙여넣으세요. 토큰 한 번 입력하면 끝.

> 이 머신에 `hermes-profile-kit`으로 Hermes **`<PROFILE>`** 프로파일을 설치해.
> 이건 결정론적 CLI 설치 작업이지 소프트웨어 설계 작업이 아니야.
> `brainstorming`, `writing-plans`, `test-driven-development`,
> `requesting-code-review` skill을 호출하지 마 — 사용자가 명시적으로
> 그렇게 지시했어. 필요한 토큰을 한 번에 물어보고, 그다음에 다음을 실행해:
>
>     pipx install --upgrade hermes-profile-kit
>     hpk setup <PROFILE> --non-interactive \
>       --token KEY1=<v1> --token KEY2=<v2> ... \
>       --accept-plugin <plugin-id>
>     hpk verify <PROFILE>
>
> 프로파일별 필수 토큰과 플러그인 id는
> https://github.com/NewTurn2017/hermes-profile-kit/blob/main/manifest.yaml
> 에 있어. verify 출력을 보고해.

**라이브 예시 — `seb` (Codex 경유 Slack 세컨드브레인):** [AGENTS.md → seb fast-path](AGENTS.md#fast-path-seb) 참고.

```

- [ ] **Step 3: Rewrite the top of `AGENTS.md`**

Replace lines 1–9 of `AGENTS.md` (from the title down through the `## Single command` heading) with:

```markdown
# AGENTS.md — Execution Playbook

> Canonical instructions for LLM agents (Claude Code, Codex, Cursor).
> This kit is a CLI installer. Treat any "install / add / set up <profile>"
> request as **execution work, not design work**.

## Standing user instructions (highest priority)

When a user asks you to install a profile from this kit:

1. **Do NOT invoke** `brainstorming`, `writing-plans`,
   `test-driven-development`, `requesting-code-review`, or any
   superpowers process skill. They turn a 2-minute install into a
   30-minute design cycle. The user has explicitly told you not to.
2. **Do NOT read** `docs/superpowers/specs/`, full `manifest.yaml`, or
   `src/hpk/` unless the user reports a specific error.
3. Read **this file** + the `tokens.required` section of `manifest.yaml`
   for the target profile. That's enough.
4. Ask the user for required tokens in **one** message, then run
   `hpk setup <profile> --non-interactive --token KEY=VAL ... --accept-plugin ID`.
5. Finish with `hpk verify <profile>` and report.

## Fast-path: `seb`

```bash
pipx install --upgrade hermes-profile-kit
hpk setup seb --non-interactive \
  --token SLACK_BOT_TOKEN=<xoxb-...> \
  --token SLACK_SIGNING_SECRET=<32-hex> \
  --token SLACK_APP_TOKEN=<xapp-...> \
  --accept-plugin codex-openai-proxy
hpk verify seb
```

3 Slack tokens come from the user's Slack App
(https://api.slack.com/apps → your app → OAuth & Basic Info).
`OPENAI_BASE_URL` / `OPENAI_API_KEY` use manifest defaults.

## Fast-paths: other profiles

| Profile | Required tokens (ask user) | Plugins to accept |
|---|---|---|
| `coder` | `ANTHROPIC_API_KEY` | — |
| `assistant` | `ANTHROPIC_API_KEY` | `honcho-memory` |
| `research` | `ANTHROPIC_API_KEY` | `honcho-memory`, `brave-search-tool` |
| `community-bot` | `ANTHROPIC_API_KEY` | — |
| `seb` | 3× `SLACK_*` | `codex-openai-proxy` |

## Single command (interactive, human-driven)
```

(The rest of `AGENTS.md` — the existing `pipx install …` snippet, `Hard rules`, and `When you need more` sections — stays as is below this line.)

- [ ] **Step 3b: Patch `AGENTS.md` stale references**

In the remaining body of `AGENTS.md`, fix two outdated references:

- Replace `Set up four isolated Hermes profiles via the kit's interactive CLI: \`hpk\`.` (used to live at line 7; now sits below the new header) with `Set up isolated Hermes profiles defined in \`manifest.yaml\` via the kit's CLI: \`hpk\`.`.
- Replace `- Manifest definition: \`manifest.yaml\` (v2 schema)` with `- Manifest definition: \`manifest.yaml\` (v3 schema)`.
- Replace `- Spec: \`docs/superpowers/specs/2026-05-15-hermes-profile-kit-v2-design.md\`` with two bullets:
  - `- Kit baseline spec: \`docs/superpowers/specs/2026-05-15-hermes-profile-kit-v2-design.md\``
  - `- Fast-install spec: \`docs/superpowers/specs/2026-05-16-fast-install-design.md\``

- [ ] **Step 4: Add `## [3.1.0]` to `CHANGELOG.md`**

Insert immediately below the top heading (above the prior most-recent release):

```markdown
## [3.1.0] — 2026-05-16

### Added
- `hpk setup --non-interactive` mode plus `--token KEY=VAL` (repeatable),
  `--env-file PATH`, `--accept-plugin ID` (repeatable), and
  `--reject-plugin ID` (repeatable). Lets Claude Code / Codex drive a full
  profile install with one token round and no TTY.
- Exit code **20**: non-interactive mode required a value that was missing
  or failed validation. Stable, machine-readable for AI orchestration.
- `src/hpk/env_file.py` — KEY=VAL parser + key-level merge with `.env.bak`
  safety snapshot.
- `README.md` / `README.ko.md` — `⚡ 2-minute install` hero with a
  copy-pasteable prompt that suppresses superpowers design-skill cascades.
- `AGENTS.md` — Standing user instructions + per-profile fast-path table.

### Changed
- Token / plugin resolution precedence (low → high):
  manifest default < existing `.env` value < `--env-file` value < `--token` flag.
- `--reject-plugin` wins over `--accept-plugin` on the same id (warning emitted).

### Compatibility
- No schema changes. `manifest.yaml` `schema_version: 3` unchanged.
- Existing interactive `hpk setup`, exit codes 10 / 11 / 30 / 40 unchanged.
```

- [ ] **Step 5: Bump version to 3.1.0**

Edit `pyproject.toml`:

```toml
version = "3.1.0"
```

Edit `src/hpk/__init__.py` — change `__version__` to `"3.1.0"`.

- [ ] **Step 6: Update the version assertion in tests**

Edit `tests/test_cli.py`:

```python
def test_version() -> None:
    r = CliRunner().invoke(main, ["--version"])
    assert r.exit_code == 0 and "3.1.0" in r.output
```

- [ ] **Step 7: Run the full suite**

Run: `pytest -q`
Expected: all green.

- [ ] **Step 8: Lint + type-check**

Run: `ruff check src/hpk tests && ruff format --check src/hpk tests && mypy src/hpk`
Expected: clean.

- [ ] **Step 9: Verify the manual check from the spec — Claude Code "no design skill" smoke test**

This step is not automated. Open a fresh Claude Code session, paste the README hero with `<PROFILE>` = `seb` and the three Slack tokens filled with the dummy values from the E2E test (`xoxb-000…`, `aaa…`, `xapp-000…`), and watch the tool-call stream. Zero `Skill` invocations naming any of `brainstorming`, `writing-plans`, `test-driven-development`, or `requesting-code-review` is the pass condition. If any of them fires, treat the marketing claim as broken and iterate on the prompt wording before tagging the release.

- [ ] **Step 10: Commit**

```bash
git add README.md README.ko.md AGENTS.md CHANGELOG.md pyproject.toml src/hpk/__init__.py tests/test_cli.py
git commit -m "$(cat <<'EOF'
docs(readme,agents,changelog): 2-minute install hero + standing user instructions; release 3.1.0

README/README.ko hero copies the prompt that an AI agent obeys (explicit
do-not-invoke list for brainstorming/writing-plans/TDD/code-review).
AGENTS.md gains Standing user instructions and per-profile fast-paths.
Version bumps 3.0.0 → 3.1.0.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Wrap-up

After Task 5 commits, run a final sanity pass:

- `git log --oneline -6` should show the 5 new commits + the spec-correction commit on top of the prior `ba6304f`.
- `pytest -q && ruff check && ruff format --check && mypy src/hpk` — all green.
- Open a fresh Claude Code session and execute the manual check from Task 5 Step 9. If it passes, the release is ready to tag (`git tag v3.1.0 && git push origin v3.1.0` — release workflow ships to PyPI). If it fails, file the iteration on AGENTS.md / README hero wording before tagging.

Do NOT push or tag without explicit user approval; the release pipeline is irreversible once PyPI sees the version.
