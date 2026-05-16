# hermes-profile-kit

Interactive multi-profile setup utility for [Hermes Agent](https://github.com/NousResearch/hermes-agent).

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/hermes-profile-kit.svg)](https://pypi.org/project/hermes-profile-kit/)
[![CI](https://github.com/NewTurn2017/hermes-profile-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/NewTurn2017/hermes-profile-kit/actions/workflows/ci.yml)

> 🇰🇷 [한국어 README](README.ko.md)

## TL;DR — 어디서부터 읽어야 하나 / Where to start

| 당신은… / You are… | 여기로 / Read |
|---|---|
| 👤 키트를 처음 써보는 사람 / First-time human user | ↓ [사람은 이렇게 / For humans](#사람은-이렇게--for-humans) |
| 🤖 LLM 에이전트 (Claude / Cursor / Hermes 자신) | ↓ [LLM은 이렇게 / For LLM agents](#llm은-이렇게--for-llm-agents) + canonical [AGENTS.md](AGENTS.md) |
| 🔧 메인테이너 / Repo maintainer | ↓ [Operating this repo](#operating-this-repo) |

## Repository facts (machine-readable)

```yaml
package: hermes-profile-kit
version: 3.0.0
schema_version: 3
language: python>=3.10
cli_entrypoint: hpk
manifest_path: manifest.yaml
profiles_path: profiles/
verified_commands_index: build/cmd_index.json   # CI-managed
verified_commands_doc:   docs/commands.md       # CI-managed
upstream:
  repo: https://github.com/NousResearch/hermes-agent
  pinned_commit: 5621fc44     # current; see manifest.yaml for live value
hard_rules_doc: AGENTS.md     # canonical playbook for LLM agents
```

## 사람은 이렇게 / For humans

### Prerequisites
- Python ≥ 3.10
- [Hermes Agent](https://github.com/NousResearch/hermes-agent) installed (binary on PATH; version ≥ 0.12.0)
- `~/.local/bin` on PATH (for profile aliases)

### Install + run
```bash
pipx install hermes-profile-kit
hpk setup
```

The wizard walks you through each profile in `manifest.yaml`:
1. Verifies Hermes is installed and recent enough.
2. Creates the Hermes profile if absent.
3. Copies `SOUL.md` + `config.yaml` from the kit template.
4. Seeds `.env` from `.env.example` (mode `0600`, never overwrites existing).
5. Prompts for required + optional tokens with provider-specific guidance (BotFather URL, Slack app docs, …).
6. Asks before enabling each recommended plugin (Honcho memory, Brave search, …).

### Re-run safely
`hpk setup` is idempotent. Existing `.env` files are preserved; existing profiles aren't re-created.

### Customizing a profile
| Goal | Edit |
|---|---|
| Change model | `~/.hermes/profiles/<name>/config.yaml` |
| Change persona | `~/.hermes/profiles/<name>/SOUL.md` |
| Add new profile | `profiles/<name>/{SOUL.md,config.yaml,.env.example}` + add entry to `manifest.yaml` → `hpk setup` |
| Force template overwrite | `hpk setup --force` |

API keys live in `~/.hermes/profiles/<name>/.env` (plain text, `chmod 600`). The kit deliberately does not pretend to encrypt them.

## LLM은 이렇게 / For LLM agents

**Canonical playbook:** [AGENTS.md](AGENTS.md). Read that first.

### Where to look (in order)
1. `AGENTS.md` — hard rules, single-command happy path.
2. `manifest.yaml` — declarative source of truth for profiles, tokens, plugins.
3. `docs/commands.md` (auto-generated) — every Hermes command the kit will invoke.
4. `build/cmd_index.json` — same data, structured for programmatic matching.
5. `src/hpk/` — implementation; layout is in `docs/superpowers/specs/2026-05-15-hermes-profile-kit-v2-design.md`.

### Hard rules (do not violate)
1. NEVER write secrets to git-tracked files. Tokens belong in `~/.hermes/profiles/<name>/.env` (mode 0600, gitignored via `.env`).
2. NEVER guess token values. Empty prompt → leave `FILL_IN_*` and surface in the summary.
3. NEVER touch the default Hermes profile (`~/.hermes/` root, not `~/.hermes/profiles/`).
4. NEVER invoke a Hermes command not present in `build/cmd_index.json`.
5. NEVER run `gateway install` or other side-effectful commands without explicit human approval.

### Useful invocations
```bash
hpk doctor                 # verify hpk's own state (hermes presence, manifest validity)
hpk verify [profile...]    # run `hermes doctor` per profile + FILL_IN scan
hpk plugin list            # show recommended_plugins per profile
hpk setup --skip-tokens    # base + plugins without interactive token prompts
hpk setup --skip-plugins   # base + tokens, skip plugin prompts
```

### Exit-code map (from `hpk setup` / preflight)
| Exit | Meaning |
|---|---|
| 0 | success |
| 10 | hermes not installed |
| 11 | hermes version < `min_hermes_version` |
| 30 | other preflight error / verify found FILL_IN or failing doctor |
| 40 | manifest invalid or unknown plugin id |

## Profiles

| Profile | Role | Model tier | Channels | Recommended plugins |
|---|---|---|---|---|
| `coder` | Full-stack dev assistant | Sonnet | CLI | — |
| `assistant` | Personal daily assistant | Sonnet | CLI + Telegram | Honcho |
| `research` | Web-search-backed research | Opus | CLI | Honcho, Brave search |
| `community-bot` | Korean dev community helper | Haiku | Telegram + Discord | — |
| `seb` | Second-brain controller (Obsidian + NotebookLM via Slack) | openai-codex | Slack | codex-openai-proxy |

## Plugins

| Plugin | Type | What it does |
|---|---|---|
| `honcho-memory` | Hermes-upstream | External long-term memory via Honcho (Plastic Labs). |
| `brave-search-tool` | Hermes-upstream | Web search tool backed by Brave Search API. |
| `codex-openai-proxy` | **Kit-local** (`install_path`) | Local OpenAI-compat HTTP bridge to the `codex` CLI — lets `seb` (and any other openai-codex–tier profile) treat Codex as an OpenAI-compatible backend. |

Hermes-upstream plugins go through `hermes` subcommands verified against `build/cmd_index.json`. Kit-local plugins live under `scripts/<plugin-id>/` and are wired into the wizard via `plugin.install_path`.

## Commands cheat sheet

```bash
hpk setup [profile...]                # interactive wizard
hpk verify [profile...]               # hermes doctor + FILL_IN scan
hpk doctor                            # hpk's own health
hpk reset [profile...] --yes          # remove kit-created profiles
hpk plugin list                       # list recommended plugins
hpk plugin enable PROFILE PLUGIN_ID
hpk plugin disable PROFILE PLUGIN_ID  # currently a manual-guidance stub
hpk sync --upstream PATH [--dry-run]  # local drift check (CI does it daily)
```

## Operating this repo

For maintainers — what to do when…

### …upstream Hermes ships a new commit
- Daily: CI does it automatically (`.github/workflows/upstream-sync.yml` runs at 06:00 UTC, clones upstream, regenerates `build/cmd_index.json` + `docs/commands.md`, updates `manifest.yaml`'s `upstream.pinned_*`, opens a PR on drift).
- Manually:
  ```bash
  git clone https://github.com/NousResearch/hermes-agent /tmp/hermes
  hpk sync --upstream /tmp/hermes               # check
  python scripts/regen_docs.py --upstream /tmp/hermes \
    --out build/cmd_index.json --docs docs/commands.md --pinned-commit "$(git -C /tmp/hermes rev-parse --short HEAD)"
  python scripts/update_manifest_pin.py \
    --commit ... --version ... --verified-at ...
  ```

### …you want to release a new version
1. Bump `version` in `pyproject.toml` and `src/hpk/__init__.py` (must match).
2. Update `CHANGELOG.md` (Keep-a-Changelog format).
3. Commit + push to `main`.
4. Tag: `git tag -a v<ver> -m "..." && git push origin v<ver>`.
5. `.github/workflows/release.yml` builds and publishes to PyPI via Trusted Publisher (already configured).

### …CI fails
- Matrix: Python 3.10 / 3.11 / 3.12 on Linux. Steps: `pip install -e ".[dev]"` → `ruff check` → `mypy` → `pytest`.
- Reproduce locally:
  ```bash
  python -m venv .venv && source .venv/bin/activate
  pip install -e ".[dev]"
  ruff check src tests scripts
  mypy src/hpk
  pytest -v
  ```

### …you add a new profile / plugin / token provider
| Thing added | Files to touch |
|---|---|
| Profile | `profiles/<name>/{SOUL.md,config.yaml,.env.example}` + entry in `manifest.yaml` `profiles:` |
| Hermes-upstream plugin | Add to `manifest.yaml` `plugins:` with `upstream_command` matching an entry in `build/cmd_index.json` |
| Kit-local plugin | Add `scripts/<plugin-id>/` + manifest entry with `install_path` instead of `upstream_command` |
| Token provider | `src/hpk/tokens/<provider>.py` with `Handler` + register in `src/hpk/tokens/__init__.py` |

### Pre-commit local gate
No git hooks are installed by default. Run before pushing:
```bash
ruff check src tests scripts && ruff format --check src tests scripts && mypy src/hpk && pytest
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `HermesNotInstalledError` at preflight | `hermes` not on PATH | Install hermes-agent, ensure it's on PATH |
| `HermesVersionTooOldError` | Installed Hermes < `manifest.min_hermes_version` | Upgrade Hermes |
| `~/.local/bin not on PATH` warning | shell PATH missing it | Add `export PATH="$HOME/.local/bin:$PATH"` to your shell rc |
| `hpk verify` reports `FILL_IN` | Token still placeholder | Edit `~/.hermes/profiles/<n>/.env` or re-run `hpk setup` |
| `manifest invalid` | YAML / schema mismatch | Check `schema_version: 3`, run `python -c "from hpk.manifest import load_manifest; from pathlib import Path; load_manifest(Path('manifest.yaml'))"` |
| `release.yml` failing with `invalid-publisher` | PyPI Trusted Publisher not registered for this repo | Configure at https://pypi.org/manage/account/publishing/ |

## Architecture

```text
                          ┌─────────────────────────┐
                          │     manifest.yaml       │  (declarative source of truth)
                          │   schema_version: 3     │
                          └────────────┬────────────┘
                                       │ parses
                                       ▼
┌─────────────────┐         ┌────────────────────────┐         ┌──────────────────┐
│  hpk (Click)    │ ──────▶ │ hpk.wizard / verify    │ ──────▶ │ hpk.hermes       │ ─▶ hermes (subprocess)
│  setup/verify/  │         │ phase A (base)         │         │ run_profile_*    │
│  doctor/plugin/ │         │ phase B (tokens)       │         │ run_doctor       │
│  reset/sync     │         │ phase C (plugins)      │         │ run_raw          │
└─────────────────┘         └────────────────────────┘         └──────────────────┘
                                       │
                                       │ asks
                                       ▼
                          ┌─────────────────────────┐
                          │  hpk.tokens.<provider>  │ (anthropic, slack, telegram, discord, brave, exa, openai-codex)
                          └─────────────────────────┘

CI loop (daily):
  upstream-sync.yml → clone hermes-agent → scripts/regen_docs.py (AST-walks hermes_cli/main.py via hpk.codegen.argparse_walker)
                  → build/cmd_index.json + docs/commands.md → drift PR
```

## Links

- 📖 [AGENTS.md](AGENTS.md) — canonical LLM playbook
- 📋 [CHANGELOG.md](CHANGELOG.md) — version history (Keep-a-Changelog)
- 🧱 [docs/concepts.md](docs/concepts.md) — Hermes profile isolation model
- 🔧 [docs/commands.md](docs/commands.md) — auto-generated verified Hermes commands
- 🛠️ [docs/troubleshooting.md](docs/troubleshooting.md) — extended troubleshooting
- 📐 [docs/superpowers/specs/](docs/superpowers/specs/) — design specs (v2 + seb profile)
- 📝 [docs/superpowers/plans/](docs/superpowers/plans/) — implementation plans
- 🐍 [PyPI: hermes-profile-kit](https://pypi.org/project/hermes-profile-kit/)
- 🏠 [Hermes Agent (upstream)](https://github.com/NousResearch/hermes-agent)

## License

MIT. See [LICENSE](LICENSE).
