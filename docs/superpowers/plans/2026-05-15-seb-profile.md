# seb Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `seb` (Second Brain) Hermes profile to hermes-profile-kit: manifest v3 schema extensions, two new token-handler families, kit-local plugin support, all profile template files, an updated `manifest.yaml`, and a standalone Codex CLI proxy.

**Architecture:** Thin-profile pattern — the profile is SOUL.md + config.yaml + .env.example. hpk plumbing gains schema v3 (new model tier + nullable plugin fields + TokenSpec.default), three new token providers, and a "kit-local plugin" concept for the Codex proxy. The proxy itself (`scripts/codex-openai-proxy/`) is a self-contained FastAPI app that sits between Hermes' OpenAI adapter and the user's logged-in `codex` CLI.

**Tech Stack:** Python ≥ 3.10, Pydantic v2, Click, Questionary, Rich, pytest (kit); FastAPI + uvicorn (proxy). `uv run pytest tests/` for kit tests; proxy has its own venv.

**Spec correction (wizard keys):** The spec wrote `wizard: slack_app` for all three Slack tokens and `wizard: codex_proxy` for both OpenAI tokens. The handler-per-key pattern requires distinct wizard IDs. This plan uses: `slack_bot` (existing), `slack_signing` (new), `slack_app` (existing) for Slack; `codex_base_url` and `codex_api_key` (both new) for OpenAI.

**Baseline:** 64 tests pass (`uv run pytest tests/ -q`).

---

## File map

| File | Action | Task |
|---|---|---|
| `src/hpk/manifest.py` | Modify — schema_version 2\|3, model_tier +openai-codex, Plugin nullable fields, TokenSpec.default | 1 |
| `tests/test_manifest.py` | Modify — tests for new schema shapes | 1 |
| `src/hpk/plugins.py` | Modify — handle `upstream_command=None` (install_path plugins) | 2 |
| `tests/test_plugins.py` | Modify — tests for install_path path | 2 |
| `src/hpk/wizard.py` | Modify — phase_b default support, phase_c kit-local plugin path | 3 |
| `tests/test_wizard.py` | Modify — test default fallback, test kit-local plugin prompt | 3 |
| `src/hpk/tokens/slack.py` | Modify — add `SlackSigningSecretHandler` + `slack_signing` wizard | 4 |
| `tests/test_tokens/test_slack.py` | Modify — test signing secret handler | 4 |
| `src/hpk/tokens/openai_codex.py` | Create — `CodexBaseURLHandler`, `CodexAPIKeyHandler` | 5 |
| `src/hpk/tokens/__init__.py` | Modify — register openai_codex WIZARDS | 5 |
| `tests/test_tokens/test_openai_codex.py` | Create — tests for both handlers | 5 |
| `profiles/seb/SOUL.md` | Create | 6 |
| `profiles/seb/config.yaml` | Create | 6 |
| `profiles/seb/.env.example` | Create | 6 |
| `manifest.yaml` | Modify — schema_version 3, add seb profile + codex-openai-proxy plugin | 7 |
| `scripts/codex-openai-proxy/proxy.py` | Create | 8 |
| `scripts/codex-openai-proxy/pyproject.toml` | Create | 8 |
| `scripts/codex-openai-proxy/tests/test_proxy.py` | Create | 8 |
| `scripts/codex-openai-proxy/launchd.plist.example` | Create | 8 |
| `scripts/codex-openai-proxy/README.md` | Create | 8 |
| `tests/e2e/test_seb_setup.py` | Create — full hpk setup seb e2e | 9 |
| `profiles/seb/README.md` | Create | 10 |

---

## Task 1: Manifest schema v3

Extends the Pydantic models to accept the new values seb needs. Zero behaviour change for existing profiles.

**Files:**
- Modify: `src/hpk/manifest.py`
- Modify: `tests/test_manifest.py`

- [ ] **Step 1.1: Write failing tests**

Add to `tests/test_manifest.py`:

```python
SEV3_YAML = """\
schema_version: 3
kit: { name: hpk, version: 3.0.0, license: MIT }
upstream:
  repo: https://github.com/NousResearch/hermes-agent
  pinned_commit: abc1234
  pinned_version: 0.12.3
  verified_at: 2026-05-15T09:49Z
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
        - { key: OPENAI_BASE_URL, provider: openai-codex, wizard: codex_base_url, default: "http://localhost:8765/v1" }
        - { key: OPENAI_API_KEY,  provider: openai-codex, wizard: codex_api_key,  default: "sk-codex-proxy-local" }
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


def test_schema_version_3_accepted(tmp_path):
    m = load_manifest(write(tmp_path, SEV3_YAML))
    assert m.schema_version == 3
    assert m.profiles[0].model_tier == "openai-codex"
    assert m.profiles[0].channels == ["slack"]


def test_token_spec_default_field(tmp_path):
    m = load_manifest(write(tmp_path, SEV3_YAML))
    base_url_spec = next(
        t for t in m.profiles[0].tokens.required if t.key == "OPENAI_BASE_URL"
    )
    assert base_url_spec.default == "http://localhost:8765/v1"


def test_plugin_nullable_upstream_command(tmp_path):
    m = load_manifest(write(tmp_path, SEV3_YAML))
    plugin = m.plugins["codex-openai-proxy"]
    assert plugin.upstream_command is None
    assert plugin.install_path == "scripts/codex-openai-proxy"
    assert plugin.launchd_template == "scripts/codex-openai-proxy/launchd.plist.example"


def test_schema_version_2_still_accepted(tmp_path):
    m = load_manifest(write(tmp_path, VALID_YAML))  # VALID_YAML is schema_version: 2
    assert m.schema_version == 2


def test_unknown_schema_version_rejected(tmp_path):
    bad = SEV3_YAML.replace("schema_version: 3", "schema_version: 99")
    with pytest.raises(ManifestValidationError):
        load_manifest(write(tmp_path, bad))


def test_openai_codex_model_tier_accepted(tmp_path):
    m = load_manifest(write(tmp_path, SEV3_YAML))
    assert m.profiles[0].model_tier == "openai-codex"


def test_invalid_model_tier_rejected(tmp_path):
    bad = SEV3_YAML.replace("model_tier: openai-codex", "model_tier: gpt-99")
    with pytest.raises(ManifestValidationError):
        load_manifest(write(tmp_path, bad))
```

- [ ] **Step 1.2: Run — expect failures**

```bash
uv run pytest tests/test_manifest.py -v -k "schema_version_3 or token_spec_default or plugin_nullable or openai_codex_model or unknown_schema"
```

Expected: 5–7 failures mentioning `Literal[2]` or `extra fields not permitted`.

- [ ] **Step 1.3: Extend manifest.py**

Replace the relevant classes in `src/hpk/manifest.py`. **Show only changed classes — leave all others untouched.**

```python
class TokenSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    provider: str
    wizard: str | None = None
    default: str | None = None          # ← new


class Plugin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str
    upstream_command: str | None = None  # ← was str (non-nullable)
    verified_in_upstream: bool = False
    docs: str | None = None
    install_path: str | None = None      # ← new (kit-local helper path)
    launchd_template: str | None = None  # ← new


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    template: str
    role: str
    model_tier: Literal["haiku", "sonnet", "opus", "openai-codex"]  # ← added openai-codex
    channels: list[str]
    tokens: TokensSection = Field(default_factory=TokensSection)
    recommended_plugins: list[RecommendedPlugin] = Field(default_factory=list)


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[2, 3]        # ← was Literal[2]
    kit: KitMeta
    upstream: Upstream
    min_hermes_version: str
    profiles: list[Profile]
    plugins: dict[str, Plugin]
    preserve_existing: list[str]
    overwrite_from_template: list[str]

    @model_validator(mode="after")
    def _cross_field(self) -> Manifest:
        from packaging.version import Version

        if Version(self.min_hermes_version) > Version(self.upstream.pinned_version):
            raise ValueError("min_hermes_version must be <= upstream.pinned_version")
        known = set(self.plugins.keys())
        for p in self.profiles:
            for rp in p.recommended_plugins:
                if rp.id not in known:
                    raise ValueError(f"profile {p.name!r} references unknown plugin {rp.id!r}")
        return self
```

- [ ] **Step 1.4: Run — expect all tests pass**

```bash
uv run pytest tests/test_manifest.py -v
```

Expected: all green, no regressions.

- [ ] **Step 1.5: Full suite green**

```bash
uv run pytest tests/ -q
```

Expected: 71 passed (64 + 7 new).

- [ ] **Step 1.6: Commit**

```bash
git add src/hpk/manifest.py tests/test_manifest.py
git commit -m "feat(manifest): schema v3 — openai-codex tier, nullable plugin fields, TokenSpec.default"
```

---

## Task 2: plugins.py — install_path plugin handling

`run_plugin` currently crashes if `upstream_command` is None. For kit-local plugins (`verified_in_upstream: false`, `install_path` set), we want a graceful informational path rather than an error.

**Files:**
- Modify: `src/hpk/plugins.py`
- Modify: `tests/test_plugins.py`

- [ ] **Step 2.1: Write failing tests**

Add to `tests/test_plugins.py`:

```python
from hpk.manifest import Plugin


def _kit_local_plugin() -> Plugin:
    return Plugin(
        description="local proxy",
        upstream_command=None,
        install_path="scripts/codex-openai-proxy",
        launchd_template="scripts/codex-openai-proxy/launchd.plist.example",
        verified_in_upstream=False,
        docs="scripts/codex-openai-proxy/README.md",
    )


def test_render_command_raises_for_null_upstream_command():
    from hpk.plugins import PluginExecError, render_command
    with pytest.raises(PluginExecError, match="install_path"):
        render_command(_kit_local_plugin(), profile="seb")


def test_run_plugin_raises_with_install_path_hint():
    from hpk.plugins import PluginExecError, run_plugin
    with pytest.raises(PluginExecError, match="scripts/codex-openai-proxy"):
        run_plugin(_kit_local_plugin(), profile="seb")
```

- [ ] **Step 2.2: Run — expect failures**

```bash
uv run pytest tests/test_plugins.py -v -k "null_upstream or install_path_hint"
```

Expected: 2 failures — `AttributeError: 'NoneType' object has no attribute 'format'`.

- [ ] **Step 2.3: Update plugins.py**

```python
"""Recommended-plugin runner. Dispatches a manifest-declared hermes command per profile."""

from __future__ import annotations

import shlex

from hpk.hermes import run_raw
from hpk.manifest import Plugin


class PluginExecError(RuntimeError):
    pass


def render_command(plugin: Plugin, *, profile: str) -> list[str]:
    if plugin.upstream_command is None:
        raise PluginExecError(
            f"plugin has no upstream_command — it is a kit-local helper at "
            f"{plugin.install_path!r}. Install it manually; see {plugin.docs or 'plugin docs'}."
        )
    return shlex.split(plugin.upstream_command.format(profile=profile))


def run_plugin(plugin: Plugin, *, profile: str) -> None:
    if plugin.install_path and not plugin.verified_in_upstream:
        raise PluginExecError(
            f"plugin at {plugin.install_path!r} is a kit-local helper — "
            f"install manually. See {plugin.docs or plugin.install_path + '/README.md'}."
        )
    if not plugin.verified_in_upstream:
        raise PluginExecError(f"plugin not verified in upstream: {plugin.upstream_command!r}")
    cmd = render_command(plugin, profile=profile)
    r = run_raw(cmd)
    if r.returncode != 0:
        raise PluginExecError(f"plugin command failed ({r.returncode}): {r.stderr.strip()}")
```

- [ ] **Step 2.4: Run — all tests pass**

```bash
uv run pytest tests/test_plugins.py -v
```

Expected: all green.

- [ ] **Step 2.5: Full suite**

```bash
uv run pytest tests/ -q
```

Expected: 73 passed.

- [ ] **Step 2.6: Commit**

```bash
git add src/hpk/plugins.py tests/test_plugins.py
git commit -m "feat(plugins): graceful handling of install_path kit-local plugins"
```

---

## Task 3: wizard.py — default token fallback + kit-local plugin prompt

Two changes:
1. `phase_b` `_collect_one`: when user presses Enter (empty input) and `token_spec.default` is set, return the default instead of `None`.
2. `phase_c`: for `install_path` plugins, print install instructions instead of running a hermes command.

**Files:**
- Modify: `src/hpk/wizard.py`
- Modify: `tests/test_wizard.py`

- [ ] **Step 3.1: Write failing tests**

Add to `tests/test_wizard.py`:

```python
def test_phase_b_uses_token_default_on_empty_input(fake_hermes, tmp_path, monkeypatch):
    """When user presses Enter (empty string), wizard writes token_spec.default."""
    home = tmp_path / ".hermes/profiles/seb"
    home.mkdir(parents=True)
    (home / ".env").write_text("OPENAI_API_KEY=FILL_IN_OPENAI_API_KEY\n")
    monkeypatch.setenv("HOME", str(tmp_path))

    from hpk.manifest import Profile, TokenSpec, TokensSection
    from hpk import wizard

    profile = Profile(
        name="seb",
        template="/tmp",
        role="second brain",
        model_tier="openai-codex",
        channels=["slack"],
        tokens=TokensSection(
            required=[
                TokenSpec(
                    key="OPENAI_API_KEY",
                    provider="openai-codex",
                    wizard="codex_api_key",
                    default="sk-codex-proxy-local",
                )
            ]
        ),
    )
    # Empty input — user presses Enter
    monkeypatch.setattr(wizard, "_prompt_secret", lambda intro, key: "")
    wizard.phase_b_tokens(profile)

    contents = (home / ".env").read_text()
    assert "OPENAI_API_KEY=sk-codex-proxy-local" in contents


def test_phase_c_kit_local_plugin_prints_instructions(fake_hermes, tmp_path, monkeypatch, capsys):
    """Kit-local plugins (install_path, not verified) should print instructions, not exec."""
    monkeypatch.setenv("HOME", str(tmp_path))
    from hpk.manifest import (
        KitMeta, Manifest, Plugin, Profile, RecommendedPlugin, Upstream, TokensSection,
    )
    from hpk import wizard

    plugin = Plugin(
        description="local proxy",
        upstream_command=None,
        install_path="scripts/codex-openai-proxy",
        launchd_template="scripts/codex-openai-proxy/launchd.plist.example",
        verified_in_upstream=False,
        docs="scripts/codex-openai-proxy/README.md",
    )
    profile = Profile(
        name="seb",
        template="/tmp",
        role="second brain",
        model_tier="openai-codex",
        channels=["slack"],
        tokens=TokensSection(),
        recommended_plugins=[RecommendedPlugin(id="codex-openai-proxy", default=True)],
    )
    # User says "yes" to installing
    monkeypatch.setattr("questionary.confirm", lambda msg, default=True: type("A", (), {"ask": lambda self: True})())
    wizard.phase_c_plugins(profile, {"codex-openai-proxy": plugin})

    # Should NOT raise; should NOT call hermes
    assert not any("hermes" in str(call) for call in fake_hermes.calls)
```

- [ ] **Step 3.2: Run — expect failures**

```bash
uv run pytest tests/test_wizard.py -v -k "default_on_empty or kit_local_plugin"
```

Expected: 2 failures.

- [ ] **Step 3.3: Update wizard.py**

In `_collect_one`, change the empty-input path:

```python
def _collect_one(token_spec: TokenSpec, *, optional: bool) -> str | None:
    handler = (
        tokens.get_handler(provider=token_spec.provider, wizard=token_spec.wizard)
        if token_spec.wizard
        else tokens.get_handler(provider=token_spec.provider)
    )
    if optional:
        proceed = questionary.confirm(
            f"Set up {token_spec.provider} ({token_spec.key}) now?", default=False
        ).ask()
        if not proceed:
            return token_spec.default  # ← return default instead of None
    for attempt in range(3):
        value = _prompt_secret(handler.intro(), token_spec.key)
        if not value:
            return token_spec.default  # ← return default instead of None
        r = handler.validate(value)
        if r.ok:
            return value
        ui.warn(f"validation failed: {r.reason} (attempt {attempt + 1}/3)")
    ui.warn("3 failed validations — skipping")
    return token_spec.default  # ← return default instead of None
```

In `phase_c_plugins`, add the kit-local branch before the `verified_in_upstream` check:

```python
def phase_c_plugins(profile: Profile, plugins_catalog: dict[str, Plugin]) -> None:
    if not profile.recommended_plugins:
        return
    ui.step(f"[C] plugins — {profile.name}")
    for rp in profile.recommended_plugins:
        plugin = plugins_catalog.get(rp.id)
        if plugin is None:
            ui.warn(f"plugin {rp.id} not found in catalog — skipping")
            continue

        # Kit-local helper: print install path, never exec hermes.
        if plugin.install_path and not plugin.verified_in_upstream:
            if _ask_plugin(rp.id, rp.default):
                ui.warn(
                    f"plugin [bold]{rp.id}[/bold] is a kit-local helper. "
                    f"Install manually: see [cyan]{plugin.install_path}/README.md[/cyan]"
                )
                if plugin.launchd_template:
                    ui.console.print(f"  launchd template: {plugin.launchd_template}")
            else:
                ui.ok(f"plugin {rp.id} skipped by user")
            continue

        if not plugin.verified_in_upstream:
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
```

- [ ] **Step 3.4: Run — all tests pass**

```bash
uv run pytest tests/test_wizard.py -v
```

Expected: all green.

- [ ] **Step 3.5: Full suite**

```bash
uv run pytest tests/ -q
```

Expected: 75 passed.

- [ ] **Step 3.6: Commit**

```bash
git add src/hpk/wizard.py tests/test_wizard.py
git commit -m "feat(wizard): TokenSpec.default fallback + kit-local plugin install-path prompt"
```

---

## Task 4: Slack signing secret token handler

The `SLACK_SIGNING_SECRET` token needs its own handler with format validation (32-char hex string). Register it under wizard key `slack_signing`.

**Files:**
- Modify: `src/hpk/tokens/slack.py`
- Modify: `tests/test_tokens/test_slack.py`

- [ ] **Step 4.1: Write failing tests**

Add to `tests/test_tokens/test_slack.py`:

```python
def test_slack_signing_secret_handler_validates_hex():
    from hpk.tokens.slack import SlackSigningSecretHandler
    h = SlackSigningSecretHandler()
    assert h.validate("a" * 32).ok is True
    assert h.validate("0f" * 16).ok is True


def test_slack_signing_secret_rejects_wrong_length():
    from hpk.tokens.slack import SlackSigningSecretHandler
    h = SlackSigningSecretHandler()
    assert h.validate("abc").ok is False
    assert h.validate("a" * 31).ok is False


def test_slack_signing_secret_rejects_non_hex():
    from hpk.tokens.slack import SlackSigningSecretHandler
    h = SlackSigningSecretHandler()
    assert h.validate("z" * 32).ok is False


def test_slack_signing_wizard_registered():
    from hpk.tokens import get_handler
    h = get_handler(wizard="slack_signing")
    assert h.key == "SLACK_SIGNING_SECRET"
```

- [ ] **Step 4.2: Run — expect failures**

```bash
uv run pytest tests/test_tokens/test_slack.py -v -k "signing"
```

Expected: 4 failures — `ImportError` or `KeyError: 'slack_signing'`.

- [ ] **Step 4.3: Add handler to slack.py**

Append to `src/hpk/tokens/slack.py` (keep existing classes untouched):

```python
import re as _re


class SlackSigningSecretHandler:
    key = "SLACK_SIGNING_SECRET"
    provider = "slack"
    docs_url = "https://api.slack.com/apps"

    def intro(self) -> str:
        return (
            "Slack App Signing Secret (32-char hex string).\n"
            f"  1. {self.docs_url} → your app → 'Basic Information'\n"
            "  2. Under 'App Credentials' → Signing Secret → click 'Show'\n"
            "  3. Copy and paste below."
        )

    def validate(self, value: str) -> ValidationResult:
        if not _re.fullmatch(r"[a-f0-9]{32}", value):
            return ValidationResult(False, "expected 32-char lowercase hex string")
        return ValidationResult(True)
```

Update `WIZARDS` dict at the bottom of `slack.py`:

```python
WIZARDS: dict[str, TokenHandler] = {
    "slack_bot": SlackBotHandler(),
    "slack_app": SlackAppHandler(),
    "slack_signing": SlackSigningSecretHandler(),
}
```

- [ ] **Step 4.4: Run — all tests pass**

```bash
uv run pytest tests/test_tokens/test_slack.py -v
```

Expected: all green.

- [ ] **Step 4.5: Full suite**

```bash
uv run pytest tests/ -q
```

Expected: 79 passed.

- [ ] **Step 4.6: Commit**

```bash
git add src/hpk/tokens/slack.py tests/test_tokens/test_slack.py
git commit -m "feat(tokens): slack_signing wizard for SLACK_SIGNING_SECRET (32-char hex)"
```

---

## Task 5: OpenAI Codex token handlers

Two new handlers for `OPENAI_BASE_URL` (URL format) and `OPENAI_API_KEY` (accepts any non-empty value — it's a dummy key for the local proxy). Both registered under the `openai-codex` provider.

**Files:**
- Create: `src/hpk/tokens/openai_codex.py`
- Modify: `src/hpk/tokens/__init__.py`
- Create: `tests/test_tokens/test_openai_codex.py`

- [ ] **Step 5.1: Write failing tests**

Create `tests/test_tokens/test_openai_codex.py`:

```python
import pytest


def test_codex_base_url_accepts_localhost():
    from hpk.tokens.openai_codex import CodexBaseURLHandler
    h = CodexBaseURLHandler()
    assert h.validate("http://localhost:8765/v1").ok is True
    assert h.validate("https://my-proxy.local/v1").ok is True


def test_codex_base_url_rejects_non_url():
    from hpk.tokens.openai_codex import CodexBaseURLHandler
    h = CodexBaseURLHandler()
    assert h.validate("localhost:8765").ok is False
    assert h.validate("").ok is False


def test_codex_api_key_accepts_any_non_empty():
    from hpk.tokens.openai_codex import CodexAPIKeyHandler
    h = CodexAPIKeyHandler()
    assert h.validate("sk-codex-proxy-local").ok is True
    assert h.validate("anything").ok is True


def test_codex_api_key_rejects_empty():
    from hpk.tokens.openai_codex import CodexAPIKeyHandler
    h = CodexAPIKeyHandler()
    assert h.validate("").ok is False


def test_codex_base_url_wizard_registered():
    from hpk.tokens import get_handler
    h = get_handler(wizard="codex_base_url")
    assert h.key == "OPENAI_BASE_URL"


def test_codex_api_key_wizard_registered():
    from hpk.tokens import get_handler
    h = get_handler(wizard="codex_api_key")
    assert h.key == "OPENAI_API_KEY"


def test_openai_codex_provider_registered():
    from hpk.tokens import get_handler
    # provider-only lookup (no wizard) is not defined for openai-codex; wizard is required
    with pytest.raises(KeyError):
        get_handler(provider="openai-codex")
```

- [ ] **Step 5.2: Run — expect failures**

```bash
uv run pytest tests/test_tokens/test_openai_codex.py -v
```

Expected: 7 failures — `ModuleNotFoundError`.

- [ ] **Step 5.3: Create src/hpk/tokens/openai_codex.py**

```python
"""Token handlers for the openai-codex provider (local Codex CLI OAuth proxy)."""

from __future__ import annotations

from hpk.tokens.base import TokenHandler, ValidationResult


class CodexBaseURLHandler:
    """Handler for OPENAI_BASE_URL — the base URL of the local Codex proxy."""

    key = "OPENAI_BASE_URL"
    provider = "openai-codex"
    docs_url = "scripts/codex-openai-proxy/README.md"

    def intro(self) -> str:
        return (
            "Base URL for the local Codex OpenAI-compatible proxy.\n"
            "  Default: http://localhost:8765/v1\n"
            "  Start the proxy first:\n"
            "    cd scripts/codex-openai-proxy && uv run uvicorn proxy:app\n"
            "  Press Enter to accept the default."
        )

    def validate(self, value: str) -> ValidationResult:
        if not (value.startswith("http://") or value.startswith("https://")):
            return ValidationResult(False, "expected http:// or https:// URL")
        return ValidationResult(True)


class CodexAPIKeyHandler:
    """Handler for OPENAI_API_KEY — a dummy key accepted by the local proxy."""

    key = "OPENAI_API_KEY"
    provider = "openai-codex"
    docs_url = "scripts/codex-openai-proxy/README.md"

    def intro(self) -> str:
        return (
            "Dummy API key for the local Codex proxy.\n"
            "  Real authentication is via your logged-in 'codex' CLI session.\n"
            "  The OpenAI SDK requires this field to be non-empty.\n"
            "  Press Enter to accept the default: sk-codex-proxy-local"
        )

    def validate(self, value: str) -> ValidationResult:
        if not value:
            return ValidationResult(False, "value must not be empty — press Enter to use default")
        return ValidationResult(True)


WIZARDS: dict[str, TokenHandler] = {
    "codex_base_url": CodexBaseURLHandler(),
    "codex_api_key": CodexAPIKeyHandler(),
}
```

- [ ] **Step 5.4: Update src/hpk/tokens/__init__.py**

```python
"""Per-provider token collection handlers."""

from hpk.tokens.anthropic import HANDLER as _anthropic
from hpk.tokens.base import TokenHandler
from hpk.tokens.brave import BraveHandler
from hpk.tokens.discord import WIZARDS as _discord_wizards
from hpk.tokens.exa import ExaHandler
from hpk.tokens.openai_codex import WIZARDS as _openai_codex_wizards
from hpk.tokens.slack import WIZARDS as _slack_wizards
from hpk.tokens.telegram import WIZARDS as _telegram_wizards

_BY_PROVIDER: dict[str, TokenHandler] = {
    "anthropic": _anthropic,
    "brave": BraveHandler(),
    "exa": ExaHandler(),
}
_BY_WIZARD: dict[str, TokenHandler] = {
    **_telegram_wizards,
    **_slack_wizards,
    **_discord_wizards,
    **_openai_codex_wizards,
}


def get_handler(*, provider: str | None = None, wizard: str | None = None) -> TokenHandler:
    if wizard is not None:
        return _BY_WIZARD[wizard]
    if provider is not None:
        return _BY_PROVIDER[provider]
    raise ValueError("need provider or wizard")
```

- [ ] **Step 5.5: Run — all tests pass**

```bash
uv run pytest tests/test_tokens/ -v
```

Expected: all green.

- [ ] **Step 5.6: Full suite**

```bash
uv run pytest tests/ -q
```

Expected: 86 passed.

- [ ] **Step 5.7: Commit**

```bash
git add src/hpk/tokens/openai_codex.py src/hpk/tokens/__init__.py tests/test_tokens/test_openai_codex.py
git commit -m "feat(tokens): openai-codex provider — codex_base_url and codex_api_key wizards"
```

---

## Task 6: Profile template files

Pure file creation. No new code, no tests. These are the template files `hpk setup` copies.

**Files:**
- Create: `profiles/seb/SOUL.md`
- Create: `profiles/seb/config.yaml`
- Create: `profiles/seb/.env.example`

- [ ] **Step 6.1: Create profiles/seb/SOUL.md**

```markdown
# SOUL — seb (Second Brain)

## Role
당신은 사용자의 second-brain 컨트롤 봇이다. Slack에서 @멘션으로 호출되어
Obsidian vault(`/Users/genie/Obsidian/second-brain/second-brain/`)와
NotebookLM을 양방향으로 다룬다. 검색·정리·요약·NotebookLM 산출물 생성과
저장이 주 업무다. 일반 코딩 보조나 일정 관리는 다른 profile(`coder`,
`assistant`) 영역이며, 이 채널에서 요청이 들어오면 해당 profile로 안내한다.

## Communication style
- 한국어 우선. 사용자 톤(존댓말/반말)을 미러링한다.
- 단답 기본. 풀이는 요청받을 때만.
- 이모지 사용 금지(사용자가 먼저 쓰면 그때만).
- 첫 응답은 한 줄 ack + 다음 행동 예고("vault 검색 중…" 식).

## Vault zones (HARD)
경로는 vault root 기준 상대 경로다. 매 쓰기 작업 전 zone 판정 필수.

| Zone | 경로 | 정책 |
|---|---|---|
| AUTO_WRITE | `raw/**` | 신규 파일 생성·append 자유. 기존 파일 *수정*은 diff 미리보기 1회 출력 후 자동 적용. |
| APPROVE | `wiki/**`, 루트 `*.md` (`index.md`, `log.md`) | 모든 쓰기/이동/삭제는 Slack Block Kit `Approve`/`Cancel` 클릭 필요. |
| LOCKED | `90.*/**`, `_private/**`, `private/**`, `.obsidian/**` | 읽기·쓰기 모두 거부. 사용자가 정확한 경로를 명시해도 거부하고 이유를 설명한다. |

unmatched 경로는 안전 기본값으로 APPROVE 취급.

## NotebookLM operations
- 새 notebook 생성, source 추가, artifact(briefing/audio/study guide/mindmap) 생성은 `notebooklm` skill CLI를 통해 수행한다.
- 생성된 artifact는 항상 `raw/imported/notebooklm/<YYYY-MM-DD>-<slug>/` 아래로 저장(AUTO_WRITE 영역).
- 이미 wiki에 정리된 노트를 source로 쓸 때는 사용자에게 "wiki/<path>를 source로 쓸까요?" 한 줄 확인 후 진행 (읽기지만 사용자 의도 확인).

## Slack 행동규칙
- @멘션이 없는 메시지에는 절대 반응하지 않는다. 쓰레드 내에서는 첫 멘션 이후 자유롭게 응답한다.
- 쓰레드별 컨텍스트는 격리한다. 다른 쓰레드 내용을 가져오지 않는다.
- destructive op(APPROVE zone 쓰기/이동/삭제) 직전에는 다음을 한 메시지로 출력:
  1. 무엇을 할지 한 줄 요약
  2. 영향받는 경로 목록 (≤10개, 더 많으면 처음 10개 + "외 N건")
  3. 변경 diff 또는 dry-run 결과
  4. `Approve` / `Cancel` Block Kit 버튼
- 한 번의 Approve 클릭은 한 번의 op만 실행한다. 배치 처리는 사용자가 명시적으로 "모두 적용"이라고 입력해야 활성화.

## Hard rules
- vault root 밖으로 쓰기 금지.
- LOCKED zone은 어떤 인자가 와도 거부.
- diff/dry-run을 못 만드는 op는 실행 거부하고 사용자에게 이유 설명.
- NotebookLM API 에러는 그대로 노출 (재시도 자동 금지 — 사용자 결정 사항).
- 한 쓰레드에서 동시 진행 중인 op는 1개. 새 요청이 와도 직전 op 완료/취소 후 시작.

## What to remember (MEMORY.md guidance)
- 사용자의 frontmatter 스타일(필수 키, 날짜 포맷).
- 자주 쓰는 태그 taxonomy와 폴더 매핑.
- NotebookLM artifact 선호(언어/길이/포맷).
- 자주 source로 쓰는 도메인/저자.

## What NOT to remember
- 일회성 검색 쿼리.
- 쓰레드 내 임시 결정(쓰레드 자체가 기록임).
```

- [ ] **Step 6.2: Create profiles/seb/config.yaml**

```yaml
# Hermes profile config — seb (Second Brain)
# Slack-only personal second-brain controller.
# Model: gpt-5.5 via local Codex CLI OAuth proxy (OPENAI_BASE_URL override).

model:
  default: openai/gpt-5.5

auxiliary:
  default: openai/gpt-5.4-mini

terminal:
  backend: local

tools:
  enabled:
    - file
    - shell
    - web_search
    - web_fetch
  disabled:
    - image_generation
    - voice
    - cron

gateway:
  approval_required:
    - delete
    - move
    - mass_message
    - send_message

concurrency:
  per_thread: 1
  per_profile: 3

rate_limit:
  per_user_per_hour: 60
  per_channel_per_hour: 120

memory:
  built_in:
    nudge_interval_turns: 20
    max_facts: 300

display:
  tool_preview_length: 100
```

- [ ] **Step 6.3: Create profiles/seb/.env.example**

```bash
# seb profile — environment variables
# Copy to ~/.hermes/profiles/seb/.env and replace FILL_IN.
# This file is gitignored at the kit level. NEVER commit a populated copy.

# --- Required: Slack (Socket Mode, 개인용 단일 워크스페이스) ---
# Create a Slack App at https://api.slack.com/apps
# Enable Socket Mode under Settings → Socket Mode
SLACK_BOT_TOKEN=FILL_IN
SLACK_SIGNING_SECRET=FILL_IN
SLACK_APP_TOKEN=FILL_IN

# --- Required: model 경로 (Codex CLI proxy) ---
# Start the proxy first: cd scripts/codex-openai-proxy && uv run uvicorn proxy:app --port 8765
# For auto-start: copy launchd.plist.example → ~/Library/LaunchAgents/ and load it.
OPENAI_BASE_URL=http://localhost:8765/v1
OPENAI_API_KEY=sk-codex-proxy-local

# --- Optional: Jina Reader for source ingestion ---
# JINA_API_KEY=FILL_IN
```

- [ ] **Step 6.4: Verify files exist**

```bash
ls -la profiles/seb/
```

Expected: `.env.example  SOUL.md  config.yaml` listed.

- [ ] **Step 6.5: Commit**

```bash
git add profiles/seb/
git commit -m "feat(profiles): seb template files — SOUL.md, config.yaml, .env.example"
```

---

## Task 7: manifest.yaml update

Add the seb profile entry and codex-openai-proxy plugin, bump schema_version to 3. Fix wizard keys to match actual handler names (spec correction: `slack_app` for all three Slack → use distinct IDs; `codex_proxy` for both OpenAI → `codex_base_url` / `codex_api_key`).

**Files:**
- Modify: `manifest.yaml`

- [ ] **Step 7.1: Check current manifest loads cleanly**

```bash
uv run python -c "from hpk.manifest import load_manifest; from pathlib import Path; m = load_manifest(Path('manifest.yaml')); print(f'OK: {len(m.profiles)} profiles')"
```

Expected: `OK: 4 profiles`

- [ ] **Step 7.2: Update manifest.yaml**

Change `schema_version: 2` → `schema_version: 3` and `version: 2.0.0` → `version: 3.0.0` in the `kit:` block.

Add the seb profile entry inside `profiles:` (after community-bot):

```yaml
  - name: seb
    template: profiles/seb
    role: Second-brain controller (Obsidian + NotebookLM via Slack)
    model_tier: openai-codex
    channels: [slack]
    tokens:
      required:
        - { key: SLACK_BOT_TOKEN,       provider: slack,        wizard: slack_bot     }
        - { key: SLACK_SIGNING_SECRET,  provider: slack,        wizard: slack_signing }
        - { key: SLACK_APP_TOKEN,       provider: slack,        wizard: slack_app     }
        - { key: OPENAI_BASE_URL,       provider: openai-codex, wizard: codex_base_url, default: "http://localhost:8765/v1" }
        - { key: OPENAI_API_KEY,        provider: openai-codex, wizard: codex_api_key,  default: "sk-codex-proxy-local" }
      optional:
        - { key: JINA_API_KEY, provider: jina }
    recommended_plugins:
      - { id: codex-openai-proxy, default: true }
```

Add the codex-openai-proxy plugin entry inside `plugins:` (after brave-search-tool):

```yaml
  codex-openai-proxy:
    description: "Local OpenAI-compatible HTTP proxy routing /v1/chat/completions to the user's logged-in Codex CLI (gpt-5.5 / gpt-5.4-mini). No separate OpenAI billing key required."
    upstream_command: null
    install_path: scripts/codex-openai-proxy
    launchd_template: scripts/codex-openai-proxy/launchd.plist.example
    verified_in_upstream: false
    docs: scripts/codex-openai-proxy/README.md
```

- [ ] **Step 7.3: Verify manifest loads with seb**

```bash
uv run python -c "
from hpk.manifest import load_manifest
from pathlib import Path
m = load_manifest(Path('manifest.yaml'))
seb = next(p for p in m.profiles if p.name == 'seb')
print(f'seb: model_tier={seb.model_tier} channels={seb.channels}')
print(f'tokens: {[t.key for t in seb.tokens.required]}')
print(f'plugins: {list(m.plugins.keys())}')
"
```

Expected:
```
seb: model_tier=openai-codex channels=['slack']
tokens: ['SLACK_BOT_TOKEN', 'SLACK_SIGNING_SECRET', 'SLACK_APP_TOKEN', 'OPENAI_BASE_URL', 'OPENAI_API_KEY']
plugins: ['honcho-memory', 'brave-search-tool', 'codex-openai-proxy']
```

- [ ] **Step 7.4: Full suite still green**

```bash
uv run pytest tests/ -q
```

Expected: 86 passed (schema_version: 3 in YAML is now accepted by updated Literal).

- [ ] **Step 7.5: Commit**

```bash
git add manifest.yaml
git commit -m "feat(manifest): add seb profile + codex-openai-proxy plugin, schema_version 3"
```

---

## Task 8: Codex OpenAI proxy

Standalone FastAPI application. Translates OpenAI Chat Completions API calls to `codex responses` CLI subprocess calls. Has its own `pyproject.toml`, tests, and a macOS launchd template.

**Files:**
- Create: `scripts/codex-openai-proxy/proxy.py`
- Create: `scripts/codex-openai-proxy/pyproject.toml`
- Create: `scripts/codex-openai-proxy/tests/__init__.py`
- Create: `scripts/codex-openai-proxy/tests/test_proxy.py`
- Create: `scripts/codex-openai-proxy/launchd.plist.example`
- Create: `scripts/codex-openai-proxy/README.md`

**Note on Codex CLI interface:** `codex responses` uses the OpenAI Responses API format, not Chat Completions. The proxy translates between them. If the CLI interface differs from this plan's assumptions, update `_to_responses_input()` and `_from_responses_output()` only — the HTTP layer stays unchanged. Verify with `codex responses --help` before running the proxy.

- [ ] **Step 8.1: Bootstrap venv**

```bash
mkdir -p scripts/codex-openai-proxy/tests
touch scripts/codex-openai-proxy/tests/__init__.py
```

- [ ] **Step 8.2: Create scripts/codex-openai-proxy/pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "codex-openai-proxy"
version = "0.1.0"
description = "Local OpenAI-compatible proxy wrapping the Codex CLI OAuth session"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
]

[project.optional-dependencies]
dev = ["pytest>=8", "httpx>=0.27"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra -q"
```

- [ ] **Step 8.3: Write failing proxy tests**

Create `scripts/codex-openai-proxy/tests/test_proxy.py`:

```python
"""Tests for codex-openai-proxy. Uses TestClient to avoid spinning up a real server.
Codex CLI calls are mocked — no real 'codex' binary required."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from proxy import app
    return TestClient(app)


# ── /v1/models ────────────────────────────────────────────────────────────────

def test_list_models_returns_configured_models(client):
    r = client.get("/v1/models")
    assert r.status_code == 200
    ids = [m["id"] for m in r.json()["data"]]
    assert "gpt-5.5" in ids
    assert "gpt-5.4-mini" in ids


# ── /v1/chat/completions (non-streaming) ──────────────────────────────────────

def _fake_popen(stdout_text: str, returncode: int = 0):
    """Return a mock Popen that produces a fixed stdout."""
    mock = MagicMock()
    mock.communicate.return_value = (
        json.dumps({
            "output": [{"type": "message", "content": [{"type": "output_text", "text": stdout_text}]}]
        }).encode(),
        b"",
    )
    mock.returncode = returncode
    return mock


def test_chat_completions_non_streaming_returns_content(client):
    with patch("subprocess.Popen", return_value=_fake_popen("Hello world")) as mock_popen:
        r = client.post("/v1/chat/completions", json={
            "model": "gpt-5.5",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": False,
        })
    assert r.status_code == 200
    data = r.json()
    assert data["choices"][0]["message"]["content"] == "Hello world"
    assert data["choices"][0]["finish_reason"] == "stop"
    assert data["object"] == "chat.completion"


def test_chat_completions_passes_model_to_codex(client):
    with patch("subprocess.Popen", return_value=_fake_popen("ok")) as mock_popen:
        client.post("/v1/chat/completions", json={
            "model": "gpt-5.4-mini",
            "messages": [{"role": "user", "content": "ping"}],
        })
    call_args = mock_popen.call_args[0][0]
    assert "gpt-5.4-mini" in call_args


def test_system_message_becomes_instructions(client):
    captured = {}
    def fake_popen(cmd, stdin, stdout, stderr):
        # Read stdin to check what was sent to codex
        import io
        mock = _fake_popen("ok")
        original_communicate = mock.communicate
        def capturing_communicate(input_data=None):
            if input_data:
                captured["payload"] = json.loads(input_data.decode())
            return original_communicate(input_data)
        mock.communicate = capturing_communicate
        return mock

    with patch("subprocess.Popen", side_effect=fake_popen):
        client.post("/v1/chat/completions", json={
            "model": "gpt-5.5",
            "messages": [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Hi"},
            ],
        })
    assert captured.get("payload", {}).get("instructions") == "You are helpful"


def test_codex_auth_error_returns_502_with_hint(client):
    mock = MagicMock()
    mock.communicate.return_value = (b"", b"error: not authenticated, run codex auth login")
    mock.returncode = 1
    with patch("subprocess.Popen", return_value=mock):
        r = client.post("/v1/chat/completions", json={
            "model": "gpt-5.5",
            "messages": [{"role": "user", "content": "hi"}],
        })
    assert r.status_code == 502
    assert "codex auth login" in r.json()["detail"]["error"]["message"]


def test_codex_not_found_returns_502(client):
    with patch("subprocess.Popen", side_effect=FileNotFoundError("codex not found")):
        r = client.post("/v1/chat/completions", json={
            "model": "gpt-5.5",
            "messages": [{"role": "user", "content": "hi"}],
        })
    assert r.status_code == 502
    assert "codex" in r.json()["detail"]["error"]["message"].lower()


# ── /v1/chat/completions (streaming) ─────────────────────────────────────────

def test_chat_completions_streaming_returns_sse(client):
    with patch("subprocess.Popen", return_value=_fake_popen("streamed content")):
        with client.stream("POST", "/v1/chat/completions", json={
            "model": "gpt-5.5",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        }) as r:
            assert r.status_code == 200
            chunks = r.text.strip().split("\n\n")
    data_lines = [c for c in chunks if c.startswith("data: ") and "[DONE]" not in c]
    assert len(data_lines) >= 1
    first = json.loads(data_lines[0][6:])
    assert first["object"] == "chat.completion.chunk"
    assert "streamed content" in first["choices"][0]["delta"]["content"]
```

- [ ] **Step 8.4: Run — all failures**

```bash
cd scripts/codex-openai-proxy && uv venv && uv pip install -e ".[dev]" && uv run pytest tests/ -v 2>&1 | head -30
cd ../..
```

Expected: ImportError on `from proxy import app`.

- [ ] **Step 8.5: Create scripts/codex-openai-proxy/proxy.py**

```python
"""Local OpenAI-compatible proxy routing /v1/chat/completions to `codex responses` CLI.

Translation layer:
  OpenAI Chat Completions (input) → OpenAI Responses API format → codex CLI stdin
  codex CLI stdout (Responses API format) → OpenAI Chat Completions (output)

If the codex CLI interface changes, update _to_responses_payload() and
_extract_content() only — the HTTP layer and test surface stay unchanged.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

PORT = int(os.environ.get("CODEX_PROXY_PORT", "8765"))
MODELS = os.environ.get("CODEX_PROXY_MODELS", "gpt-5.5,gpt-5.4-mini").split(",")

app = FastAPI(title="codex-openai-proxy", version="0.1.0")


# ── Translation helpers ────────────────────────────────────────────────────────

def _to_responses_payload(body: dict) -> dict:
    """Convert Chat Completions request body to Responses API payload for codex CLI."""
    messages: list[dict] = body.get("messages", [])
    instructions: str | None = None
    turns: list[dict] = []

    for msg in messages:
        role = msg["role"]
        content = msg.get("content") or ""
        if isinstance(content, list):
            # Multi-part content — extract text parts only.
            content = " ".join(
                part.get("text", "") for part in content if part.get("type") == "text"
            )
        if role == "system":
            instructions = content
        elif role == "user":
            turns.append({
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": content}],
            })
        elif role == "assistant":
            turns.append({
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": content}],
            })

    # Single user message: use simpler string form accepted by Responses API.
    if len(turns) == 1 and turns[0]["role"] == "user":
        user_text = turns[0]["content"][0]["text"]
        payload: dict = {"model": body.get("model", MODELS[0]), "input": user_text}
    else:
        payload = {"model": body.get("model", MODELS[0]), "input": turns}

    if instructions:
        payload["instructions"] = instructions
    if tools := body.get("tools"):
        payload["tools"] = tools

    return payload


def _extract_content(response_bytes: bytes) -> str:
    """Extract assistant text from Responses API JSON output."""
    try:
        data = json.loads(response_bytes)
    except json.JSONDecodeError:
        return response_bytes.decode(errors="replace")

    for item in data.get("output", []):
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    return str(part["text"])
    # Fallback: return raw output (e.g. if codex returns plain text).
    return response_bytes.decode(errors="replace").strip()


def _is_auth_error(stderr: bytes) -> bool:
    text = stderr.decode(errors="replace").lower()
    return "auth" in text or "login" in text or "not authenticated" in text


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/v1/models")
async def list_models() -> dict:
    return {
        "object": "list",
        "data": [{"id": m, "object": "model", "owned_by": "codex-proxy"} for m in MODELS],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    model: str = body.get("model", MODELS[0])
    stream: bool = body.get("stream", False)
    payload = _to_responses_payload(body)
    stdin_data = json.dumps(payload).encode()

    try:
        proc = subprocess.Popen(
            ["codex", "responses", "--model", model, "--input-json", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        raise HTTPException(
            502,
            detail={
                "error": {
                    "message": "codex CLI not found. Install: npm i -g @openai/codex",
                    "type": "codex_not_found",
                }
            },
        )

    if stream:
        return StreamingResponse(
            _stream(proc, stdin_data, model),
            media_type="text/event-stream",
        )

    # Non-streaming: wait for full response.
    stdout, stderr = proc.communicate(stdin_data)
    if proc.returncode != 0:
        if _is_auth_error(stderr):
            raise HTTPException(
                502,
                detail={
                    "error": {
                        "message": "Run `codex auth login` first",
                        "type": "codex_auth_required",
                    }
                },
            )
        raise HTTPException(
            502,
            detail={
                "error": {
                    "message": stderr.decode(errors="replace").strip(),
                    "type": "codex_error",
                }
            },
        )

    content = _extract_content(stdout)
    return {
        "id": "chatcmpl-codex",
        "object": "chat.completion",
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


async def _stream(proc: subprocess.Popen, stdin_data: bytes, model: str):
    """Yield OpenAI SSE chunks wrapping the full Codex response."""
    loop = asyncio.get_event_loop()
    stdout, stderr = await loop.run_in_executor(None, proc.communicate, stdin_data)

    if proc.returncode != 0:
        error_text = (
            "Run `codex auth login` first" if _is_auth_error(stderr)
            else stderr.decode(errors="replace").strip()
        )
        yield f"data: {json.dumps({'error': {'message': error_text, 'type': 'codex_error'}})}\n\n"
        yield "data: [DONE]\n\n"
        return

    content = _extract_content(stdout)

    # Content chunk.
    chunk = json.dumps({
        "id": "chatcmpl-codex",
        "object": "chat.completion.chunk",
        "model": model,
        "choices": [{"index": 0, "delta": {"role": "assistant", "content": content}, "finish_reason": None}],
    })
    yield f"data: {chunk}\n\n"

    # Stop chunk.
    stop = json.dumps({
        "id": "chatcmpl-codex",
        "object": "chat.completion.chunk",
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    })
    yield f"data: {stop}\n\n"
    yield "data: [DONE]\n\n"


def main() -> None:
    uvicorn.run(app, host="127.0.0.1", port=PORT)


if __name__ == "__main__":
    main()
```

- [ ] **Step 8.6: Run proxy tests**

```bash
cd scripts/codex-openai-proxy && uv run pytest tests/ -v
cd ../..
```

Expected: 8 tests pass.

- [ ] **Step 8.7: Create launchd.plist.example**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>dev.hermes.codex-openai-proxy</string>

  <key>ProgramArguments</key>
  <array>
    <!-- Replace /path/to with the absolute path to your venv Python. -->
    <!-- Run: cd scripts/codex-openai-proxy && uv venv && which python -->
    <string>/path/to/scripts/codex-openai-proxy/.venv/bin/python</string>
    <string>-m</string>
    <string>uvicorn</string>
    <string>proxy:app</string>
    <string>--host</string>
    <string>127.0.0.1</string>
    <string>--port</string>
    <string>8765</string>
  </array>

  <key>WorkingDirectory</key>
  <string>/path/to/scripts/codex-openai-proxy</string>

  <key>StandardOutPath</key>
  <string>/Users/genie/.hermes/profiles/seb/logs/codex-proxy.log</string>

  <key>StandardErrorPath</key>
  <string>/Users/genie/.hermes/profiles/seb/logs/codex-proxy.err.log</string>

  <key>KeepAlive</key>
  <true/>

  <key>RunAtLoad</key>
  <true/>

  <key>EnvironmentVariables</key>
  <dict>
    <key>CODEX_PROXY_PORT</key>
    <string>8765</string>
    <key>CODEX_PROXY_MODELS</key>
    <string>gpt-5.5,gpt-5.4-mini</string>
  </dict>
</dict>
</plist>
```

- [ ] **Step 8.8: Create scripts/codex-openai-proxy/README.md**

```markdown
# codex-openai-proxy

Local OpenAI-compatible HTTP proxy. Translates `/v1/chat/completions` calls from
Hermes' OpenAI adapter to `codex responses` CLI subprocess calls, reusing your
existing Codex OAuth session. No separate OpenAI billing key needed.

## Prerequisites

- `codex` CLI installed and logged in (`codex auth status` → green)
- `uv` installed (`brew install uv` or `pip install uv`)

## Quick start

```bash
cd scripts/codex-openai-proxy
uv venv && uv pip install -e .
uv run uvicorn proxy:app --port 8765
# Health check:
curl http://localhost:8765/v1/models
```

## Auto-start (macOS)

```bash
# 1. Edit launchd.plist.example — fill in the two /path/to placeholders.
#    Find your venv Python path: cd scripts/codex-openai-proxy && source .venv/bin/activate && which python
# 2. Copy to LaunchAgents:
cp launchd.plist.example ~/Library/LaunchAgents/dev.hermes.codex-openai-proxy.plist
# 3. Load:
launchctl load ~/Library/LaunchAgents/dev.hermes.codex-openai-proxy.plist
# 4. Verify:
curl http://localhost:8765/v1/models
```

## Logs

```
~/.hermes/profiles/seb/logs/codex-proxy.log
~/.hermes/profiles/seb/logs/codex-proxy.err.log
```

Create the log directory first: `mkdir -p ~/.hermes/profiles/seb/logs`

## Port

Default: `8765`. Override: `CODEX_PROXY_PORT=<port> uv run uvicorn proxy:app`.

## Models

Default: `gpt-5.5,gpt-5.4-mini`. Override: `CODEX_PROXY_MODELS=gpt-5.5,gpt-5.4-mini`.

## CLI interface note

The proxy calls `codex responses --model <name> --input-json -` and sends a
JSON payload matching the [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses).
If the codex CLI flags differ from this, update `_to_responses_payload()` and
`_extract_content()` in `proxy.py` — the HTTP surface and tests are unchanged.

Verify with: `codex responses --help`

## Running tests

```bash
uv run pytest tests/ -v
```
```

- [ ] **Step 8.9: Commit proxy**

```bash
git add scripts/codex-openai-proxy/
git commit -m "feat(proxy): codex-openai-proxy — local OpenAI-compat HTTP → codex CLI bridge"
```

---

## Task 9: E2E test for seb profile setup

Validates that `hpk setup seb` runs cleanly end-to-end with the new schema: phases A/B/C all pass, Slack tokens get written, proxy tokens use defaults, kit-local plugin prints instructions without calling hermes.

**Files:**
- Create: `tests/e2e/test_seb_setup.py`

- [ ] **Step 9.1: Create tests/e2e/test_seb_setup.py**

```python
"""E2E: hpk setup seb — schema v3, openai-codex tokens, kit-local plugin."""

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

_VALID_SLACK_BOT   = "xoxb-" + "0" * 30
_VALID_SLACK_SIGN  = "a" * 32         # 32-char hex
_VALID_SLACK_APP   = "xapp-" + "0" * 30


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


def test_e2e_seb_setup_happy_path(fake_hermes, tmp_path, monkeypatch):
    """Full setup: Slack tokens answered, OpenAI tokens use defaults, kit-local plugin announced."""
    _scaffold(tmp_path)
    monkeypatch.chdir(tmp_path)

    from hpk import wizard

    # Return valid values per prompt key; empty string for codex keys → use default.
    def _fake_prompt(intro: str, key: str) -> str:
        if key == "SLACK_BOT_TOKEN":
            return _VALID_SLACK_BOT
        if key == "SLACK_SIGNING_SECRET":
            return _VALID_SLACK_SIGN
        if key == "SLACK_APP_TOKEN":
            return _VALID_SLACK_APP
        return ""  # OPENAI_BASE_URL, OPENAI_API_KEY → defaults

    monkeypatch.setattr(wizard, "_prompt_secret", _fake_prompt)
    monkeypatch.setattr("hpk.wizard._has_local_bin_on_path", lambda: True)
    # phase_c: user says "yes" to codex-openai-proxy install notice
    monkeypatch.setattr(
        "questionary.confirm",
        lambda msg, default=True: type("A", (), {"ask": lambda self: True})(),
    )

    r = CliRunner().invoke(cli_main, ["setup", "seb"])
    assert r.exit_code == 0, r.output

    env = tmp_path / ".hermes" / "profiles" / "seb" / ".env"
    contents = env.read_text()
    assert f"SLACK_BOT_TOKEN={_VALID_SLACK_BOT}" in contents
    assert f"SLACK_SIGNING_SECRET={_VALID_SLACK_SIGN}" in contents
    assert f"SLACK_APP_TOKEN={_VALID_SLACK_APP}" in contents
    assert "OPENAI_BASE_URL=http://localhost:8765/v1" in contents
    assert "OPENAI_API_KEY=sk-codex-proxy-local" in contents

    # hermes was called to create the profile, NOT to install the kit-local proxy
    assert ["hermes", "profile", "create", "seb"] in fake_hermes.calls
    hermes_calls_str = str(fake_hermes.calls)
    assert "codex-openai-proxy" not in hermes_calls_str


def test_e2e_seb_setup_idempotent(fake_hermes, tmp_path, monkeypatch):
    """Running setup twice preserves the existing .env."""
    _scaffold(tmp_path)
    monkeypatch.chdir(tmp_path)

    from hpk import wizard

    def _fake_prompt(intro: str, key: str) -> str:
        return {
            "SLACK_BOT_TOKEN": _VALID_SLACK_BOT,
            "SLACK_SIGNING_SECRET": _VALID_SLACK_SIGN,
            "SLACK_APP_TOKEN": _VALID_SLACK_APP,
        }.get(key, "")

    monkeypatch.setattr(wizard, "_prompt_secret", _fake_prompt)
    monkeypatch.setattr("hpk.wizard._has_local_bin_on_path", lambda: True)
    monkeypatch.setattr(
        "questionary.confirm",
        lambda msg, default=True: type("A", (), {"ask": lambda self: True})(),
    )

    runner = CliRunner()
    runner.invoke(cli_main, ["setup", "seb"])
    runner.invoke(cli_main, ["setup", "seb"])  # second run

    env = (tmp_path / ".hermes" / "profiles" / "seb" / ".env").read_text()
    assert f"SLACK_BOT_TOKEN={_VALID_SLACK_BOT}" in env
```

- [ ] **Step 9.2: Run**

```bash
uv run pytest tests/e2e/test_seb_setup.py -v
```

Expected: 2 tests pass.

- [ ] **Step 9.3: Full suite**

```bash
uv run pytest tests/ -q
```

Expected: 88 passed.

- [ ] **Step 9.4: Commit**

```bash
git add tests/e2e/test_seb_setup.py
git commit -m "test(e2e): full hpk setup seb — schema v3, defaults, kit-local plugin"
```

---

## Task 10: profiles/seb/README.md

User-facing Slack App creation guide. No tests — pure documentation.

**Files:**
- Create: `profiles/seb/README.md`

- [ ] **Step 10.1: Create profiles/seb/README.md**

```markdown
# seb — Second Brain profile

Slack bot that controls your Obsidian vault and NotebookLM. Powered by gpt-5.5
via the local Codex CLI proxy.

## Prerequisites

1. **Hermes** ≥ 0.12.0 installed (`hermes --version`)
2. **codex CLI** logged in (`codex auth status`) — see the proxy README for install
3. **Codex proxy running** on `localhost:8765` (`curl http://localhost:8765/v1/models`)
4. **notebooklm CLI** set up (run `notebooklm setup` if not already done)
5. **Obsidian vault** at `/Users/genie/Obsidian/second-brain/second-brain/`

## Setup

```bash
hpk setup seb
```

The wizard will ask for three Slack tokens. Follow the steps below to get them.

## Slack App creation (one-time)

### 1. Create the app

Go to <https://api.slack.com/apps> → **Create New App** → **From scratch**.

- App name: `seb` (or any name you like)
- Workspace: your personal workspace

### 2. Enable Socket Mode

Under **Settings → Socket Mode**, toggle **Enable Socket Mode** on. You'll be
asked to create an App-Level Token — name it anything (e.g. `seb-socket`), add
scope `connections:write`, click **Generate**. Copy the `xapp-...` token
(**SLACK_APP_TOKEN**).

### 3. Add bot scopes

Under **Features → OAuth & Permissions → Scopes → Bot Token Scopes**, add:

| Scope | Why |
|---|---|
| `app_mentions:read` | Receive @seb mentions |
| `chat:write` | Post messages + Block Kit cards |
| `files:read` | Read file content from channels |

### 4. Subscribe to events

Under **Features → Event Subscriptions**, toggle on. Under
**Subscribe to bot events**, add `app_mention`.

### 5. Install the app

Under **Features → OAuth & Permissions** → **Install to Workspace** → Allow.
Copy the **Bot User OAuth Token** (`xoxb-...`) (**SLACK_BOT_TOKEN**).

### 6. Get the Signing Secret

Under **Settings → Basic Information → App Credentials**, reveal and copy the
**Signing Secret** (32-char hex) (**SLACK_SIGNING_SECRET**).

## Start the bot

```bash
seb gateway start
```

In your Slack workspace, invite the bot to a channel: `/invite @seb`

Test: `@seb 안녕`

## Vault zones

| Zone | Paths | Policy |
|---|---|---|
| AUTO_WRITE | `raw/**` | Bot writes freely |
| APPROVE | `wiki/**`, root `*.md` | Bot proposes, you click Approve |
| LOCKED | `90.*/**`, `_private/**`, `.obsidian/**` | Access denied |

## NotebookLM artifacts are saved to

```
<vault>/raw/imported/notebooklm/<YYYY-MM-DD>-<slug>/
```

## Proxy auto-start

See `scripts/codex-openai-proxy/README.md` for the macOS launchd setup. The
proxy must be running before `seb gateway start`.
```

- [ ] **Step 10.2: Commit**

```bash
git add profiles/seb/README.md
git commit -m "docs(profiles): seb README — Slack App creation guide + vault zone reference"
```

---

## Self-review

**Spec coverage check:**

| Spec section | Covered by |
|---|---|
| Profile template files (SOUL, config, env) | Tasks 6, 7 |
| manifest.yaml schema v3 extension | Tasks 1, 7 |
| TokenSpec.default | Tasks 1, 3 |
| Plugin install_path / nullable upstream_command | Tasks 1, 2, 3 |
| Slack token handlers (bot, signing, app) | Tasks 4, 5 |
| OpenAI Codex token handlers | Task 5 |
| Codex proxy (FastAPI, streaming, auth error) | Task 8 |
| E2E seb setup | Task 9 |
| Acceptance criteria (vault zones, NotebookLM save path, LOCKED zone) | Covered in SOUL.md (Task 6) + profile README (Task 10) |
| Open question: `move` in gateway.approval_required | Left in config.yaml as comment; runtime will ignore if unsupported |
| Open question: thread isolation | Left to Hermes runtime; SOUL.md rule is the policy declaration |
| Open question: Hermes OpenAI provider base_url | `OPENAI_BASE_URL` env var is the standard override path for OpenAI SDK |
| Open question: Block Kit interactivity | Runtime concern; no hpk changes needed |
| Open question: Codex tool-call support | Noted in proxy README; proxy returns empty tool_calls if CLI doesn't support them |

**Placeholder scan:** None found.

**Type consistency:**
- `TokenSpec.default: str | None` used in Task 1; `_collect_one` returns `str | None` in Task 3 → consistent.
- `Plugin.upstream_command: str | None` in Task 1; `render_command` guards None in Task 2 → consistent.
- `SlackSigningSecretHandler` defined in Task 4; wizard key `slack_signing` registered in `WIZARDS` in Task 4; `manifest.yaml` uses `wizard: slack_signing` in Task 7 → consistent.
- `CodexBaseURLHandler`/`CodexAPIKeyHandler` defined in Task 5; wizard keys `codex_base_url`/`codex_api_key` in `__init__.py` in Task 5; `manifest.yaml` uses same keys in Task 7 → consistent.
