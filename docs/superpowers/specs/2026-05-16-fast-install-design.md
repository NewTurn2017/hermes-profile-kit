# Fast install design — "2-minute install via Claude Code"

| Field | Value |
|---|---|
| Date | 2026-05-16 |
| Status | Draft (pending implementation plan) |
| Owner | genie |
| Related | `2026-05-15-hermes-profile-kit-v2-design.md` (kit baseline), `2026-05-15-seb-profile-design.md` (first profile that surfaced the problem) |
| Target version | hermes-profile-kit `3.1.0` (additive minor release) |

## 1. Problem

Yesterday's real-world install of the `seb` profile via Claude Code took 30+ minutes. The kit itself ran in seconds; the slowdown came from the AI agent auto-invoking heavyweight `superpowers` process skills (`brainstorming`, `writing-plans`, `test-driven-development`, `requesting-code-review`) because it interpreted "set up a Hermes profile" as a software-engineering task. What should have been a deterministic CLI install became a multi-round design cycle.

A second, smaller failure mode contributed: `hpk setup`'s wizard is TTY-only, so an AI agent cannot complete the token round on its own — every required token forces a hand-off to the user, and then a re-read of the wizard's next prompt.

The marketing claim "single command, AI-friendly" is technically true but not lived. We want a copy-pasteable prompt that an AI agent obeys, plus a non-interactive CLI mode so the prompt is implementable end-to-end after a single token round with the user.

## 2. Goals and non-goals

**Goals**

1. A user pasting one prompt into Claude Code (or Codex) can install any profile from `manifest.yaml` in ≤ 2 minutes, with exactly one round of "give me these tokens" between the AI and the user.
2. The prompt and `AGENTS.md` together suppress automatic invocation of `brainstorming`, `writing-plans`, `test-driven-development`, and `requesting-code-review` for install requests, via explicit user-priority instructions.
3. `hpk setup` gains a non-interactive mode that accepts all values via flags or `--env-file`, with deterministic exit codes the AI can react to.
4. Existing interactive `hpk setup` behavior is preserved unchanged.

**Non-goals**

1. Shipping a Claude Code skill package (`hermes-add-profile`) bundled with the kit. Deferred to a follow-up release; this design only optimizes the prompt-and-CLI surface.
2. A Codex CLI plugin or MCP server. Same reasoning — prompt copy is sufficient for now.
3. Encrypted token storage / 1Password integration. `.env` with mode 0600 stays.
4. Adding new profiles. The five existing profiles are the test bed.
5. Changes to the upstream `hermes` binary. The kit only wraps it.
6. Changes to `manifest.yaml` schema (`schema_version` stays at 3).

**Success criteria**

- On a fresh macOS account, a user with pre-issued tokens pastes the README's "2-minute install" prompt into Claude Code, answers one token-collection message, and reaches `hpk verify <profile>` exit 0 — the only human action is pasting tokens once.
- New E2E test `tests/e2e/test_non_interactive_setup.py` reproduces this for `seb` (the heaviest required-token profile) without any interactive prompt.
- Hand-checking the README prompt in a fresh Claude Code session confirms `brainstorming` / `writing-plans` / `test-driven-development` / `requesting-code-review` do not auto-fire.

## 3. CLI design — `hpk setup --non-interactive`

### 3.1 New flags on `hpk setup`

| Flag | Repeatable | Purpose |
|---|---|---|
| `--token KEY=VAL` | yes | Inject a single token value without prompting |
| `--env-file PATH` | no | Load multiple `KEY=VAL` lines from a file (`#` comments allowed) |
| `--accept-plugin ID` | yes | Force-enable a recommended plugin |
| `--reject-plugin ID` | yes | Force-skip a recommended plugin |
| `--non-interactive` | no | Fail rather than prompt when a required value is missing |

Existing flags (`--force`, `--skip-tokens`, `--skip-plugins`, profile positional args) are untouched and remain orthogonal.

### 3.2 Token value precedence (low → high)

1. `manifest.yaml`'s `TokenSpec.default` (already supported by schema v3).
2. The value already present in the destination `~/.hermes/profiles/<name>/.env` (preserved as today).
3. Values loaded from `--env-file`.
4. Values from `--token` flags.
5. Interactive prompt — only when `--non-interactive` is *not* set and the value is still missing.

### 3.3 Plugin decision precedence

1. `manifest.yaml`'s `recommended_plugins[].default: true|false`.
2. `--accept-plugin` / `--reject-plugin` overrides. If a plugin appears in both lists, `--reject-plugin` wins and the wizard logs a warning.
3. Interactive y/n — only when `--non-interactive` is not set.

Under `--non-interactive`, any plugin without an explicit flag falls back to its manifest `default`; the wizard does not re-confirm.

### 3.4 `--non-interactive` semantics

- A *required* token with no value after step 3.2 → fail fast with exit **20** and a machine-readable message naming the missing key(s) ("AI: ask the user for these tokens and re-run with `--token KEY=VAL ...`").
- An *optional* token with no value → leave `FILL_IN_*` in `.env`, matching the existing interactive behavior. Reported in the summary; not an error.
- Validation failure on any value passed via flag or file → exit **20** with the key and the failure reason from the provider-specific validator.

### 3.5 `.env` merge policy (P1 — key-level merge)

When the destination `.env` already exists and `--token` or `--env-file` provides values:

- The wizard updates only the keys named in the flags. Other keys are left untouched.
- Before any write to an existing `.env`, the wizard makes a sibling backup at `.env.bak` (overwritten each run). Cheap safety net for the rare case where the user fed in the wrong value.
- `--force` continues to mean "overwrite template files (`SOUL.md`, `config.yaml`)" and is independent of `.env` behavior.

### 3.6 Unknown identifiers

- A `--token KEY=VAL` whose `KEY` is not in the target profile's `tokens.required ∪ tokens.optional` → exit **40** (reuses the existing "manifest invalid / unknown id" code) with a list of valid keys for the profile.
- An `--accept-plugin` / `--reject-plugin` ID not in that profile's `recommended_plugins` → exit **40** with the valid IDs.

### 3.7 Exit code map (after this change)

| Code | Meaning | Status |
|---|---|---|
| 0 | success | unchanged |
| 10 | hermes not installed | unchanged |
| 11 | hermes version too old | unchanged |
| **20** | **non-interactive: required value missing or invalid** | **new** |
| 30 | other preflight error / verify found FILL_IN | unchanged |
| 40 | manifest invalid or unknown id | unchanged (extended to cover unknown `--token` / `--accept-plugin` ids) |

### 3.8 Token-handler reuse (no refactor needed)

`TokenHandler` already exposes `validate(value: str) -> ValidationResult` separately from any prompt loop (the loop lives in `wizard._collect_one`). The flag path simply calls the same `handler.validate(value)` and treats `ValidationResult.ok == False` as exit 20. No handler-side change required.

The wizard does need a helper that, given a `Profile` and a token `KEY`, returns the matching `TokenSpec` (so the flag path can look up which handler to invoke). This helper lives in `wizard.py` alongside the existing collection code.

### 3.9 `.env` merge module

A new `src/hpk/env_file.py` owns parsing `--env-file`, merging into `.env`, and writing the `.env.bak` snapshot. Single responsibility; isolated from `wizard.py` so it can be unit-tested without touching the wizard's flow.

## 4. Prompt and docs design

### 4.1 README `⚡ 2-minute install` hero (added above the TL;DR table)

A single template prompt that an end user copies. Placeholders `<PROFILE>`, `KEY=<v>`, `<plugin-id>` are filled either by the user or by the AI from `manifest.yaml`. The prompt has three load-bearing pieces:

1. The phrase "deterministic CLI install, not a software-design task" — semantically contradicts the `brainstorming` skill's "creating features, building components, adding functionality" trigger description.
2. An explicit "do not invoke `brainstorming`, `writing-plans`, `test-driven-development`, or `code-review` skills — the user has explicitly instructed you not to" line — leverages the published `using-superpowers` priority rule that user instructions outrank skill defaults.
3. The literal command sequence (`pipx install`, `hpk setup … --token … --accept-plugin …`, `hpk verify`) so there is no interpretive room.

Both `README.md` and `README.ko.md` get the same hero, in their respective languages, with cross-links to `AGENTS.md` for fast-path tables.

### 4.2 `AGENTS.md` rewrite

The current `AGENTS.md` is short but does not address the auto-skill problem. The new structure:

1. Header reframing the kit as "a CLI installer; treat install requests as execution, not design".
2. A "Standing user instructions" section that names the four skills not to invoke, gives the reason ("they turn a 2-minute install into a 30-minute design cycle"), and tells the agent which files *not* to read by default (`docs/superpowers/specs/`, `src/hpk/`, full `manifest.yaml`).
3. A `Fast-path: seb` block — the exact non-interactive command, with notes on where the user gets the Slack tokens.
4. A `Fast-paths: other profiles` table — one row per profile, listing required tokens to ask for and plugins to accept.
5. The existing `Single command (interactive)`, `Hard rules`, and `When you need more` sections kept beneath, for the human-driven path.

The fast-path table is hand-maintained against `manifest.yaml`. A CI lint (cheap regex scan) is *not* in scope for this release; the table is small and changes only when profiles change.

### 4.3 Why the explicit "do not invoke" line works

The `superpowers:using-superpowers` skill's own instruction priority list places user instructions above skill defaults. Naming the skills in the user's request makes the instruction *explicit*, not merely implied — which is the priority-1 condition. Naming the skills also defeats the "if 1% chance, invoke" rule for the listed ones, because invoking them would directly violate an explicit user instruction.

## 5. Testing

| Test | What it proves |
|---|---|
| `tests/test_env_file.py` (new) | `env_file` parses comments and blanks; merges keys without disturbing siblings; `.env.bak` written; backup overwritten on re-run; merging into an absent `.env` creates it with mode 0600. |
| `tests/test_wizard_non_interactive.py` (new) | Value precedence `manifest default < .env < --env-file < --token` holds in `phase_b_tokens`; missing required raises the exit-20 condition; unknown KEY raises exit-40 condition; `--accept-plugin` + `--reject-plugin` on same ID → reject wins with warning. |
| `tests/test_cli.py` (extend) | Each new flag is recognized by Click; exit codes propagate (20, 40) from wizard errors. |
| `tests/e2e/test_non_interactive_setup.py` (new) | A full `hpk setup seb --token ... --accept-plugin codex-openai-proxy --non-interactive` run, with `hermes` mocked, completes with no `questionary` read; `~/.hermes/profiles/seb/.env` has all required keys filled. |

Existing `tests/e2e/test_seb_setup.py` and all unit tests must remain green.

## 6. Rollout

### 6.1 Files touched

| File | Change |
|---|---|
| `src/hpk/cli.py` | Five new flags on `setup` |
| `src/hpk/wizard.py` | Precedence logic, plugin decision logic, exit-20 branch |
| `src/hpk/tokens/__init__.py` | (unchanged — `validate()` already on the protocol) |
| `src/hpk/tokens/<provider>.py` (each) | (unchanged) |
| `src/hpk/env_file.py` | New module — parse `--env-file`, merge into `.env`, write `.env.bak` |
| `tests/test_env_file.py` | New |
| `tests/test_wizard_non_interactive.py` | New |
| `tests/test_cli.py` | Extend with flag-recognition + exit-code propagation |
| `tests/e2e/test_non_interactive_setup.py` | New |
| `README.md` | `⚡ 2-minute install` hero above TL;DR table |
| `README.ko.md` | Same hero, Korean |
| `AGENTS.md` | New header, Standing user instructions, Fast-path blocks; existing sections retained below |
| `CHANGELOG.md` | `## [3.1.0]` — Added (5 flags, exit 20, `.env` merge, README/AGENTS hero), Changed (token handler refactor) |
| `pyproject.toml` | `version = "3.1.0"` |
| `src/hpk/__init__.py` | `__version__ = "3.1.0"` |

Not touched: `manifest.yaml` (schema stays 3, no profile changes), `docs/commands.md` (auto-generated, no hermes command changes), upstream-sync workflow.

### 6.2 Commit plan (5 commits, one PR)

1. `feat(env): key-level env_file helper with .env.bak safety net` — new module + unit tests.
2. `feat(wizard): value/plugin precedence + NonInteractiveMissingError for --token / --env-file / --accept-plugin / --reject-plugin / --non-interactive` — wizard logic (no CLI surface yet).
3. `feat(cli): wire non-interactive flags on hpk setup; map errors to exit 20/40` — Click integration + cli test extension.
4. `test(e2e): non-interactive seb setup completes without interactive prompts` — regression guard for the 2-minute claim.
5. `docs(readme,agents,changelog): 2-minute install hero + standing user instructions + 3.1.0 release` — marketing surface + version bump in one commit.

### 6.3 Verification gate before merge

- `ruff check && ruff format --check && mypy src/hpk && pytest` — all green.
- The new E2E test completes with zero interactive reads (assert via a stub stdin that fails on read).
- Manual check: open a fresh Claude Code session, paste the README hero with a real profile and dummy tokens, and watch the tool-call stream for any `Skill` invocation naming `brainstorming`, `writing-plans`, `test-driven-development`, or `requesting-code-review`. Zero invocations of those four is the pass condition.

### 6.4 Out-of-scope follow-ups (recorded, not committed)

- v3.2 candidate: ship a `hermes-add-profile` Claude Code skill inside the kit, so the trigger is `/hermes-add-profile seb` instead of a paste.
- v3.2 candidate: a tiny `hpk init-prompt <profile>` subcommand that prints the ready-to-paste prompt with the right tokens listed — so the user does not even need to open the README.
- Codex CLI plugin parity — depends on Codex plugin conventions stabilizing.
