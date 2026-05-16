# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [3.2.1] — 2026-05-17

### Added
- `codex-openai-proxy` 0.2.0: migrated to today's `codex exec --json -` CLI. The old `codex responses --input-json` invocation was broken against `codex-cli >= 0.130`; tests now include a gated `CODEX_PROXY_INTEGRATION=1` contract check so future CLI drift surfaces immediately.
- `mem0-memory` 0.2.0: `Store.config()` honors `MEM0_LLM_BASE_URL` / `MEM0_LLM_API_KEY` / `MEM0_LLM_MODEL` / `MEM0_EMBEDDER_PROVIDER` / `MEM0_EMBEDDER_MODEL` env vars, enabling true "zero external billing keys" mode when paired with `codex-openai-proxy` + a local `fastembed` model.
- `mem0-memory` 0.2.0: new `[local-embedder]` extra (`uv pip install -e ".[local-embedder]"`) brings in `fastembed` for OpenAI-free embeddings.
- `mem0-memory` 0.2.0: `hpk-memory doctor` now reports the active LLM / embedder mode (`proxy`, `openai-default`, or the provider name).
- `scripts/mem0-memory/README.md`: new "Modes" section documenting proxy / OpenAI / hybrid configurations.
- `profiles/seb/SOUL.md`: 1-line routing note covering the proxy mode.

### Fixed
- `mem0-memory` 0.2.0: `Store.add` no longer loses data on silent extraction failure. v3.2.0 relied on mem0 v2 raising on LLM errors, but mem0 v2 actually swallows them and returns `{"results": []}` — so the spec's "any add either becomes a fact OR a raw row" promise was broken when the LLM was misconfigured. Now `Store.add` inspects the result and falls back to `raw_facts` whenever extraction returns empty for non-empty input; the return dict gains `extracted: bool` and `raw_id: int | None` fields.
- `codex-openai-proxy` 0.2.0: terminate `codex exec` as soon as `turn.completed` / `turn.failed` is seen on stdout. codex's agent loop can hang for tens of seconds after emitting the assistant message (cleanup / telemetry), causing mem0's OpenAI client to time out before the proxy returned. With early termination plus a 90s hard timeout, every successful agent turn returns in seconds and the silent-fail symptom from the v3.2.1 PoC is resolved.

### Notes
- v3.2.0 users with `OPENAI_API_KEY` set keep working unchanged — the env-driven config blocks are additive and absent envs leave mem0 on its built-in OpenAI defaults.
- End-to-end PoC confirmation: `MEM0_LLM_BASE_URL=http://localhost:8765/v1 MEM0_EMBEDDER_PROVIDER=fastembed MEM0_EMBEDDER_MODEL=BAAI/bge-small-en-v1.5 uv run python /tmp/mem0_codex_poc.py` returned a real extracted-fact item (proxy → Codex CLI OAuth → fact extraction → Chroma → search), zero billing keys touched.

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

## [3.1.2] — 2026-05-16

### Changed
- **`seb` now uses Hermes's native `openai-codex` provider by default.**
  `profiles/seb/config.yaml` switches `model.default` from
  `openai/gpt-5.5` (a model id that Hermes routes via OpenRouter) to
  `gpt-5.5` with explicit `provider: openai-codex`. Same for `auxiliary`.
  Result: a fresh `seb chat` works against `chatgpt.com/backend-api/codex`
  using the local Codex CLI OAuth session — no proxy, no OpenAI API key,
  no 401.
- `manifest.yaml`: `OPENAI_BASE_URL` and `OPENAI_API_KEY` moved from
  `seb.tokens.required` to `tokens.optional`. They are only needed when
  the user opts in to `codex-openai-proxy`.
- `manifest.yaml`: `codex-openai-proxy` recommended plugin default
  flipped to `false`. The plugin is now an opt-in escape hatch for hosts
  where Hermes can't reach a local Codex CLI session.
- `profiles/seb/.env.example` no longer prefills `OPENAI_BASE_URL` /
  `OPENAI_API_KEY` — they're documented as comments for users who switch
  to proxy mode.
- `profiles/seb/README.md`, `AGENTS.md`, `scripts/codex-openai-proxy/README.md`
  rewritten to reflect native-first, proxy-as-escape-hatch.

### Migration
- Existing `seb` profile installs: edit `~/.hermes/profiles/seb/config.yaml`
  to remove the `openai/` prefix and add `provider: openai-codex` under
  both `model` and `auxiliary`. The kit will not auto-patch your
  populated profile — `hpk setup --force seb` will overwrite the template.
  Token round shrinks from 3 Slack + 2 OpenAI defaults to just 3 Slack.

### Fixed
- `seb chat` 401 against `openrouter.ai/api/v1` caused by the
  `openai/gpt-5.5` model id triggering Hermes's OpenRouter routing
  instead of honoring `OPENAI_BASE_URL`.

## [3.1.1] — 2026-05-16

### Added
- `profiles/seb/slack-app-manifest.json` — paste-ready Slack App manifest
  that provisions bot scopes, `app_mention` event subscription, Socket
  Mode, and interactivity in one step via `https://api.slack.com/apps`
  → Create New App → From an app manifest.
- `AGENTS.md` seb fast-path now tells AI agents to surface the manifest
  flow first (saves ~5 manual scope clicks).

### Changed
- `profiles/seb/README.md` Slack App section rewritten around the manifest
  flow; the per-scope click instructions are replaced by a single paste
  step plus three secret-retrieval steps.

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

## [3.0.0] — 2026-05-16

### Added
- `seb` profile — Slack-driven second-brain controller for Obsidian + NotebookLM, routed through the local Codex OAuth session. Ships with `SOUL.md`, `config.yaml`, `.env.example`, and a Slack App creation guide (`profiles/seb/README.md`).
- `codex-openai-proxy` plugin — local OpenAI-compatible HTTP bridge (`/v1/chat/completions`) backed by the user's logged-in `codex` CLI. Includes proxy server, `launchd.plist.example`, isolated `pyproject.toml`, and pytest suite under `scripts/codex-openai-proxy/`.
- `openai-codex` token provider with `codex_base_url` and `codex_api_key` wizards (defaults wired to `http://localhost:8765/v1` / `sk-codex-proxy-local`).
- `slack_signing` wizard for `SLACK_SIGNING_SECRET` with 32-char hex validation.
- Manifest schema v3: `TokenSpec.default` fallback value, nullable `Plugin.upstream_command`, new `model_tier: "openai-codex"`, and `plugin.install_path` / `launchd_template` fields for kit-local plugins.
- Wizard support for kit-local plugins — when `plugin.install_path` is set, the wizard prompts the user for the install location instead of running an upstream command.
- E2E test `tests/e2e/test_seb_setup.py` covering the full `hpk setup seb` happy path: schema v3 manifest, token defaults, and kit-local plugin install flow.
- Coverage tests for `hpk reset`, `hpk plugin enable` error paths, and remaining `FILL_IN` reporting in verify.

### Changed
- `hpk sync` now accepts `--upstream PATH` and forwards it to `scripts/regen_docs.py`. Without `--upstream`, it prints clear guidance and exits 0 instead of dying on an opaque argparse error.
- `Plugin.upstream_command` is now `Optional[str]` to accommodate kit-local plugins whose install is path-based rather than CLI-driven.
- Preflight failures now raise typed `PreflightError` subclasses (`HermesNotInstalledError`, `HermesVersionTooOldError`) so `cli.py` can map exit codes via `except` clauses instead of fragile substring checks on the exception message.
- `find_missing_commands` now matches command paths with token boundaries — previously a `str.endswith` substring check produced false positives (e.g. `tools enable web_search` matching `enable web_search`).

### Removed
- Unwired `--non-interactive` / `--dry-run` flags from `hpk setup`. They accepted input but the body just `del`'d them; removing them eliminates the docs/reality mismatch.

### Fixed
- Strict-mode regressions (ruff + mypy) introduced by the v3 / seb work across `codex-openai-proxy`, `codegen/validate.py`, `tests/e2e/test_seb_setup.py`, and `tests/test_wizard.py`.

### Docs
- `docs/superpowers/specs/2026-05-15-seb-profile-design.md` — design spec for the seb profile (315 lines).
- `docs/superpowers/plans/2026-05-15-seb-profile.md` — 10-task TDD implementation plan.

## [2.0.0] — 2026-05-15

### Added
- Python `hpk` CLI (Click) with subcommands: `setup`, `verify`, `doctor`, `reset`, `plugin` (list / enable / disable), `sync`.
- Interactive wizard with three phases per profile: base (template apply + atomic `.env` writes), tokens (per-provider validators), plugins (manifest-declared `recommended_plugins`).
- Token providers and handlers: `anthropic`, `telegram` (BotFather with format validation), `slack` (bot + app tokens), `discord` (devportal), `brave`, `exa`. Handler registry lookup by provider id or wizard id.
- Manifest schema v2 (pydantic) — structured `tokens.required` / `tokens.optional`, `recommended_plugins` per profile, top-level `plugins` catalog, cross-field validation, and a v1→v2 migration helper.
- Codegen pipeline: AST-based `argparse_walker.py` producing stable `{path, params, help, hidden}` command nodes; `cmd_index.py` JSON (de)serialize; `validate.py` cross-checks manifest plugin commands against the index; `regen_docs.py` argparse→index→docs pipeline.
- CI workflows: lint + type + pytest matrix for Python 3.10 / 3.11 / 3.12; daily `upstream-sync` workflow that AST-parses upstream `hermes_cli/main.py` and opens an auto-PR on drift; `release.yml` for tag-driven PyPI publish; weekly dependabot.
- E2E test covering the full `hpk setup` happy path + idempotency on rerun, backed by a `fake_hermes` fixture.
- `hermes` subprocess wrapper with `fake_hermes` test fixture.
- Preflight checks (hermes installed + version ≥ `min_hermes_version`).
- Rich-based console helpers (`ui.py`) with `err()` routed to stderr.
- PEP 561 `py.typed` marker for downstream type checking.

### Changed
- Migrated from v1 bash flow to `hpk`-driven flow. `README.md`, `AGENTS.md`, and `docs/concepts.md` rewritten accordingly.
- Manifest v1 → v2 migration (existing `manifest.yaml` backed up to `manifest.v1.yaml.bak`).
- `docs/concepts.md` notes that internal codegen filenames track the pinned upstream commit.

### Removed
- v1 bash scripts: `scripts/install.sh`, `scripts/verify.sh`, `scripts/reset.sh` (replaced by `hpk` CLI).

### Fixed
- `manifest.load_manifest` catches `yaml.YAMLError` and reports it cleanly; removed dead `_strip_leading_v` helper.

## [1.0.0] — Initial release (Bash-only)

### Added
- Four profile templates: `coder`, `assistant`, `research`, `community-bot` — each with `SOUL.md` (persona) + `config.yaml` (Hermes config) + `.env.example`.
- Bash installer, verify, and reset scripts under `scripts/`.
- `AGENTS.md` playbook for LLM-agent-driven setup.
- Korean `README.md` aimed at human operators.

[Unreleased]: https://github.com/NewTurn2017/hermes-profile-kit/compare/v3.2.0...HEAD
[3.2.0]: https://github.com/NewTurn2017/hermes-profile-kit/releases/tag/v3.2.0
[3.1.2]: https://github.com/NewTurn2017/hermes-profile-kit/releases/tag/v3.1.2
[3.1.1]: https://github.com/NewTurn2017/hermes-profile-kit/releases/tag/v3.1.1
[3.1.0]: https://github.com/NewTurn2017/hermes-profile-kit/releases/tag/v3.1.0
[3.0.0]: https://github.com/NewTurn2017/hermes-profile-kit/releases/tag/v3.0.0
[2.0.0]: https://github.com/NewTurn2017/hermes-profile-kit/releases/tag/v2.0.0
[1.0.0]: https://github.com/NewTurn2017/hermes-profile-kit/releases/tag/v1.0.0
