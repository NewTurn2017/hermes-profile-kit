# hermes-profile-kit v2 — Design

**Status**: Approved (sections 1–7) on 2026-05-15
**Authors**: NewTurn2017 (via brainstorming with Claude)
**Supersedes**: v1.0.0 (bash-based template kit)
**Upstream SSOT**: `/Users/genie/dev/learn/hermes-agent` (NewTurn2017 fork with `upstream` remote → `NousResearch/hermes-agent`)

---

## 0. Problem Statement

Hermes Agent is a multi-profile LLM runtime that updates daily. Users who already have Hermes installed should be able to install only this profile kit and run a single command that interactively configures four named, isolated profiles (`coder` / `assistant` / `research` / `community-bot`) — including Slack / Telegram / Discord bot tokens — without writing any unverified code or commands.

v1 was a bash + template kit. It worked for setup but had three problems:
1. Hand-written `docs/commands.md` listed Hermes commands that may or may not exist in the running version (e.g. `hermes profile alias`, `gateway uninstall`, `hermes memory setup`) — no mechanical verification.
2. No interactive token-collection flow. Users had to know which `.env` keys map to which platforms and where to obtain the tokens.
3. No mechanism to track upstream Hermes drift — kit could silently rot as Hermes evolves.

v2 fixes these three by becoming a Python CLI (`hpk`) that:
- Drives Hermes through subprocess calls (never imports Hermes internals at runtime).
- Walks Hermes' Click tree at CI time to auto-generate `docs/commands.md` and validate every Hermes command the kit references.
- Runs a daily upstream-sync GitHub Action that opens a PR when drift is detected.

---

## 1. System Boundaries

```
User
  $ hpk setup
        │
        ▼
hpk  (this project)
  Responsibilities:
    - Interactive wizard UX (rich + questionary)
    - Token collection (BotFather/Slack app/Discord devportal walkthroughs)
    - Safe .env writes (atomic, chmod 600, FILL_IN preservation)
    - Template apply (SOUL.md, config.yaml → profile home)
    - Recommended-plugin on/off dispatch
    - hermes invocation + result parsing
  Explicitly NOT:
    - Profile creation itself     (delegates: hermes profile create)
    - Model/tool selection UI     (delegates: hermes -p X model / tools)
    - Gateway lifecycle           (delegates: hermes <profile> gateway ...)
    - External memory provider    (delegates: hermes -p X memory setup ...)
        │
        ▼  subprocess: hermes ...
hermes  (NousResearch/hermes-agent, installed on user machine)
  Owns all state under ~/.hermes/profiles/*
```

**Offline CI (GitHub Actions)**
```
.github/workflows/upstream-sync.yml  (daily cron)
  1. Clone NousResearch/hermes-agent @ main
  2. Walk Click tree → build/cmd_index.json
  3. Diff against committed cmd_index.json
  4. Regen docs/commands.md
  5. Update manifest.yaml upstream.pinned_*
  6. If anything changed → open PR with drift_report.md
```

### Invariants (do not violate)
- `.env` is never auto-overwritten once seeded.
- The default `~/.hermes/` profile is never touched by the kit.
- `hpk` never imports Hermes internals at runtime — CI-time only.
- `FILL_IN_*` placeholders cause `hpk` to stop and ask, never to guess.

---

## 2. CLI Surface

Installed as `hpk` via `pipx install hermes-profile-kit`.

```
hpk                                  # default: hpk setup
hpk setup [PROFILE...] [OPTS]        # interactive wizard
hpk verify [PROFILE...]              # hermes doctor + manifest sanity
hpk reset  [PROFILE...] [--yes] [--backup]
hpk doctor                           # hpk's own health (hermes presence/version, manifest validity, codegen freshness)
hpk sync  [--dry-run]                # local upstream drift scan (CI does it daily; this is manual escape hatch)
hpk plugin list                      # show recommended_plugins per profile
hpk plugin enable  <profile> <plugin-id>
hpk plugin disable <profile> <plugin-id>
hpk --version
```

### `hpk setup` flags

| Flag | Meaning |
|---|---|
| `[PROFILE...]` | Positional. Empty = all 4 from manifest. `hpk setup coder research` = subset. |
| `--non-interactive` | Read tokens from env vars; fail if any required token missing. CI / scripted use. |
| `--dry-run` | Show every action without invoking hermes or writing files. |
| `--force` | Overwrite SOUL.md / config.yaml even if profile already exists. `.env` still preserved. |
| `--skip-tokens` | Provider keys only; skip channel tokens. |
| `--skip-plugins` | Provider keys + tokens only; skip recommended-plugin prompts. |

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Success or intentional skip |
| 10 | hermes not on PATH |
| 11 | hermes version < manifest.min_hermes_version |
| 20 | User Ctrl-C / abort |
| 30 | hermes command failed (details on stderr) |
| 40 | manifest broken / template missing |
| 50 | codegen drift detected (`hpk sync --dry-run` only) |

### Verified-only command policy

`hpk` itself never embeds a hermes command unless that command appears in `build/cmd_index.json`. CI fails if any hardcoded hermes invocation is missing from the index.

---

## 3. Wizard Flow

Each profile cycles through three phases: **(A) base** → **(B) tokens** → **(C) plugins**.

### Global preflight (once)
```
[hpk] preflight
  ✓ hermes 0.12.3 detected (manifest requires ≥ 0.12.0)
  ✓ ~/.local/bin on PATH
  ✓ manifest.yaml verified (4 profiles, codegen up-to-date as of upstream@<sha>)
```
Any failure → appropriate exit code, no profile loop.

### Per-profile loop

**Phase A — base** (always)
- `hermes profile create <name>` if absent.
- Copy SOUL.md and config.yaml from `profiles/<name>/` (skipped if existed without `--force`).
- Seed `.env` from `.env.example` only if absent. `chmod 600`.

**Phase B — tokens**
- For each `required` token in `manifest.profiles[].tokens.required`: prompt (password mode).
- For each `optional` token: ask "Set up <provider> now? (y/N)". If yes:
  - Dispatch to `hpk.tokens.<provider>` handler.
  - Handler shows the official URL flow (e.g. BotFather, api.slack.com/apps, discord.com/developers).
  - Handler validates token format (regex per provider) before writing.
  - On 3 consecutive failed validations → skip with warning.

**Phase C — plugins**
- For each `manifest.profiles[].recommended_plugins[]`:
  - Skip if `plugins.<id>.verified_in_upstream` is false.
  - Prompt with default Y/N per `default:` field.
  - On yes → invoke `plugins.<id>.upstream_command` template, substituting `{profile}`.
  - Capture output; log success/failure; never abort the whole wizard on plugin failure.

### Final summary
```
Created:    coder, assistant, research, community-bot
Skipped:    (none)
Plugins on: assistant→honcho, research→honcho+brave-search
FILL_IN remaining: (none) | <list of files+lines>
Gateways not started (by design).
Next: hpk verify
```

### Idempotency
- Re-running `hpk setup` is safe: profile exists → skip create; .env exists → keep values (each key asks "overwrite? (y/N)" with default N); plugin already on → skip.
- Ctrl-C during write: atomic file replace ensures partial state is never visible.

---

## 4. Manifest v2 Schema

```yaml
schema_version: 2
kit:
  name: hermes-profile-kit
  version: 2.0.0
  license: MIT

upstream:                            # CI-managed; humans don't edit
  repo: https://github.com/NousResearch/hermes-agent
  pinned_commit: "<short-sha>"
  pinned_version: "0.12.3"
  verified_at: "2026-05-15T09:49Z"

min_hermes_version: "0.12.0"

profiles:
  - name: coder
    template: profiles/coder
    role: Full-stack development assistant
    model_tier: sonnet
    channels: [cli]
    tokens:
      required:
        - { key: ANTHROPIC_API_KEY, provider: anthropic }
      optional: []
    recommended_plugins: []

  - name: assistant
    template: profiles/assistant
    role: Personal daily assistant
    model_tier: sonnet
    channels: [cli, telegram]
    tokens:
      required:
        - { key: ANTHROPIC_API_KEY, provider: anthropic }
      optional:
        - { key: TELEGRAM_BOT_TOKEN, provider: telegram, wizard: telegram_botfather }
    recommended_plugins:
      - { id: honcho-memory, default: true }

  - name: research
    template: profiles/research
    role: Deep research with web search and citations
    model_tier: opus
    channels: [cli]
    tokens:
      required:
        - { key: ANTHROPIC_API_KEY, provider: anthropic }
      optional:
        - { key: BRAVE_SEARCH_API_KEY, provider: brave }
        - { key: EXA_API_KEY, provider: exa }
    recommended_plugins:
      - { id: honcho-memory, default: true }
      - { id: brave-search-tool, default: true }

  - name: community-bot
    template: profiles/community-bot
    role: Korean dev community helper bot
    model_tier: haiku
    channels: [telegram, discord]
    tokens:
      required:
        - { key: ANTHROPIC_API_KEY, provider: anthropic }
      optional:
        - { key: TELEGRAM_BOT_TOKEN, provider: telegram, wizard: telegram_botfather }
        - { key: DISCORD_BOT_TOKEN,  provider: discord,  wizard: discord_devportal }
    recommended_plugins: []

plugins:
  honcho-memory:
    description: "External long-term memory via Honcho (Plastic Labs). Default Hermes external memory provider."
    upstream_command: "hermes -p {profile} memory setup honcho"
    verified_in_upstream: true       # CI-managed
    docs: https://honcho.dev
  brave-search-tool:
    description: "Web search tool backed by Brave Search API"
    upstream_command: "hermes -p {profile} tools enable web_search"
    verified_in_upstream: true
    docs: https://brave.com/search/api/

preserve_existing:  [".env"]
overwrite_from_template: ["SOUL.md", "config.yaml"]
```

### Validation rules (enforced in `hpk doctor` and CI)
- Every `plugins.<id>.upstream_command` (after `{profile}` substitution) must match an entry in `build/cmd_index.json`.
- Every `tokens[].key` must exist in the corresponding `profiles/<name>/.env.example`.
- `min_hermes_version` ≤ `upstream.pinned_version` (semver).

### Field semantics
- `tokens[].wizard` is the dotted handler ID. The wizard looks up `hpk.tokens.<provider>` and calls its `WIZARDS[<wizard>]` entry. Missing handler → manifest validation error.
- `channels` is informational only (used for human-readable summary and READMEs). The wizard derives required vs optional flows from `tokens.required` / `tokens.optional`, not from `channels`.
- `recommended_plugins[].default` controls only the initial Y/N default; the user always gets the prompt unless `--skip-plugins` is passed.

---

## 5. Codegen + Upstream Sync

### 5a. Codegen pipeline (`scripts/regen_docs.py`)

```
1. Path to upstream clone passed as --upstream
2. `import hermes_cli.<main>` to obtain the Click root group
3. Walk recursively:
     for cmd in click.Context(root).command.commands.values():
       record {full_path, params[{name,opts,type,help,required,hidden}], help_text}
4. Write build/cmd_index.json (sorted, stable)
5. Emit docs/commands.md "Verified" section between AUTO-GENERATED markers
6. Diff against the committed cmd_index.json → if different in --check mode, exit 1
```

### 5b. `docs/commands.md` structure

```markdown
# Commands Reference

<!-- AUTO-GENERATED — DO NOT EDIT. Regenerated by scripts/regen_docs.py.
     Last run: <iso> against hermes-agent@<sha> -->

## Verified hermes commands (extracted from upstream Click tree)
...

<!-- END AUTO-GENERATED -->

## Kit-specific notes (hand-written)
- Commands not in the verified list above are never invoked by `hpk`.
- Last verified: <sha> on <date>.
```

### 5c. `upstream-sync.yml` workflow

```yaml
name: upstream-sync
on:
  schedule: [{ cron: "0 6 * * *" }]    # 06:00 UTC daily
  workflow_dispatch: {}
jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: git clone --depth=1 https://github.com/NousResearch/hermes-agent.git /tmp/upstream
      - run: pip install /tmp/upstream && pip install -e .
      - run: python scripts/regen_docs.py --upstream /tmp/upstream --out build/cmd_index.json --docs docs/commands.md
      - run: python scripts/update_manifest_pin.py
      - run: python scripts/drift_report.py --old <prev sha> --new <new sha> --out build/drift_report.md
      - uses: peter-evans/create-pull-request@v6
        with:
          title: "upstream sync: hermes-agent@<short-sha>"
          body-path: build/drift_report.md
          branch: upstream-sync/auto
```

### 5d. What CI catches

| Drift kind | Action |
|---|---|
| Command added | Add to cmd_index, mention in drift_report |
| Command removed | Remove from cmd_index; any kit code referencing it fails CI on the same PR |
| Param renamed | Diff highlighted in drift_report; tests likely fail |
| Plugin command path changed | manifest.plugins.<id>.verified_in_upstream auto-toggled to false; wizard hides it until manifest is updated |

---

## 6. Source Tree, Dependencies, Packaging

### 6a. Tree

```
hermes-profile-kit/
├── pyproject.toml
├── README.md                         # human-facing, hand-maintained
├── AGENTS.md                         # LLM playbook (now: "run hpk setup")
├── LICENSE
├── .gitignore
├── manifest.yaml                     # v2; upstream.* CI-managed
├── profiles/                         # templates unchanged from v1
│   ├── coder/{SOUL.md, config.yaml, .env.example, README.md}
│   ├── assistant/...
│   ├── research/...
│   └── community-bot/...
├── src/hpk/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                        # Click root
│   ├── wizard.py                     # phase A/B/C loop
│   ├── manifest.py                   # pydantic models + load
│   ├── profiles.py                   # template apply + .env seed (atomic)
│   ├── hermes.py                     # subprocess wrapper
│   ├── verify.py                     # doctor aggregation + FILL_IN scan
│   ├── plugins.py                    # recommended_plugin dispatch
│   ├── tokens/
│   │   ├── base.py                   # TokenHandler interface
│   │   ├── anthropic.py
│   │   ├── telegram.py
│   │   ├── slack.py
│   │   ├── discord.py
│   │   ├── brave.py
│   │   └── exa.py
│   ├── codegen/
│   │   ├── click_walker.py           # CI-time only
│   │   ├── cmd_index.py
│   │   └── validate.py
│   └── ui.py                         # rich console
├── scripts/
│   ├── regen_docs.py
│   ├── update_manifest_pin.py
│   └── drift_report.py
├── docs/
│   ├── concepts.md                   # isolation model (hand-maintained, but "current internal layout" boxed with pinned sha)
│   ├── commands.md                   # auto-generated + hand sections
│   ├── gateways.md
│   ├── troubleshooting.md
│   └── superpowers/specs/            # this file lives here
├── build/                            # gitignored CI artifacts
├── tests/
│   ├── conftest.py                   # fake_hermes fixture
│   ├── test_manifest.py
│   ├── test_wizard.py
│   ├── test_profiles.py
│   ├── test_tokens/
│   ├── test_codegen.py
│   └── test_drift.py
└── .github/
    ├── workflows/
    │   ├── ci.yml
    │   ├── upstream-sync.yml
    │   └── release.yml
    └── dependabot.yml
```

The v1 `scripts/install.sh`, `verify.sh`, `reset.sh` are removed. README installation instructions become `pipx install hermes-profile-kit && hpk setup`.

### 6b. Runtime dependencies (5)

| Package | Purpose |
|---|---|
| `click >= 8.1` | CLI framework (same stack as Hermes) |
| `questionary >= 2.0` | interactive prompts (password / select / confirm) |
| `rich >= 13` | formatted output |
| `pyyaml >= 6` | manifest parsing |
| `pydantic >= 2` | manifest v2 typed validation |

Dev: `pytest`, `pytest-mock`, `ruff`, `mypy`.

### 6c. `pyproject.toml`
```toml
[project]
name = "hermes-profile-kit"
version = "2.0.0"
requires-python = ">=3.10"
dependencies = ["click>=8.1", "questionary>=2.0", "rich>=13", "pyyaml>=6", "pydantic>=2"]
license = { text = "MIT" }

[project.scripts]
hpk = "hpk.cli:main"
```

---

## 7. Testing, Errors, Security

### 7a. Test pyramid

```
E2E (optional, local-only)
  Real hermes + throwaway HERMES_HOME + hpk setup --non-interactive
Integration
  monkeypatch subprocess.run; real filesystem under tmp_path
Unit
  manifest models, token validators, click_walker on toy fixture, wizard with patched questionary
```

### 7b. `fake_hermes` fixture sketch
```python
@pytest.fixture
def fake_hermes(monkeypatch, tmp_path):
    calls = []
    def fake_run(cmd, *a, **kw):
        calls.append(cmd)
        if cmd[:2] == ["hermes", "--version"]:
            return CompletedProcess(cmd, 0, stdout="Hermes Agent v0.12.3\n")
        if cmd[:3] == ["hermes", "profile", "create"]:
            (tmp_path / ".hermes/profiles" / cmd[3]).mkdir(parents=True)
            return CompletedProcess(cmd, 0)
        return CompletedProcess(cmd, 0)
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv("HOME", str(tmp_path))
    return calls
```

### 7c. Tests that must exist
- `.env` is preserved across re-runs.
- FILL_IN remaining → non-zero exit code.
- manifest plugin.upstream_command missing from cmd_index → manifest test fail.
- `regen_docs.py --check` matches the committed docs (CI gate).
- Ctrl-C mid-write produces no partial files (atomic replace).
- hermes < min_hermes_version → exit 11.

### 7d. Runtime error handling

| Situation | Behavior |
|---|---|
| `hermes` absent | message + install URL + exit 10 |
| version too low | exit 11 with min version |
| `hermes profile create` fails | stderr surfaced; skip that profile only |
| user skips token prompt | leaves FILL_IN; reported in summary |
| token validation fails 3× | warning; skip with FILL_IN intact |
| plugin command fails | log; continue (profile success unaffected) |
| Ctrl-C | atomic .env writes ensure no partial state |
| .env unwritable | exit 30 |

### 7e. Security
- Token prompts use `questionary.password` — never echo to stdout/logs.
- Secrets travel via the `.env` file path only, never via subprocess env vars (procfs leakage).
- No encryption layer in the kit — `chmod 600` + explicit "plaintext on disk" disclosure in README. False sense of security is worse than honest plaintext.

### 7f. Atomic `.env` write
```python
tmp = target.with_suffix(".env.tmp")
tmp.write_text(new_content)
tmp.chmod(0o600)
tmp.replace(target)   # POSIX-atomic
```

---

## 8. Open questions deferred from brainstorming

These were called out but intentionally pushed past v2.0.0:

1. **Plugin marketplace** (`hpk plugin install <id>` for non-manifest plugins). v2 only supports plugins declared in `manifest.yaml`.
2. **Self-update of hpk itself**. Users run `pipx upgrade hermes-profile-kit`; no in-app updater.
3. **Slack App Manifest auto-creation via API**. v2 walks the user through the web UI; programmatic creation deferred.
4. **Multi-machine config sync**. Out of scope.

---

## 9. Migration from v1

A v1 user runs `hpk setup` once. Behavior:
- If `~/.hermes/profiles/<name>/` exists with v1's templates: kit treats as existing profile, prompts for `--force` if user wants the v2 templates.
- Old `scripts/install.sh` removed in the same commit; README explains the `pipx install` path.
- Old `manifest.yaml` (schema v1) auto-migrated to v2 on first `hpk` invocation; new fields default-populated; backup written to `manifest.v1.yaml.bak`.

---

## 10. Verification Plan (post-implementation)

The "this design actually worked" check:

1. Fresh VM, install Hermes v0.12.3, `pipx install hermes-profile-kit`.
2. Run `hpk setup` with mock tokens. Expect: 4 profiles created, summary correct, FILL_IN scan green.
3. Run `hpk setup` again. Expect: idempotent, no overwrites.
4. Run `hpk verify`. Expect: all green.
5. In a fork, rename a hermes command. Push. Expect: upstream-sync PR opens within 24h with drift_report listing the rename.
