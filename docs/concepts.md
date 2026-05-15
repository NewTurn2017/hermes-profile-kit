# Concepts: Hermes Profile Isolation Model

## What a profile is

A profile = a separate Hermes home directory with its own state.

- Default profile: `~/.hermes/`
- Additional profiles: `~/.hermes/profiles/<name>/`

Internally, every Hermes path lookup goes through `get_hermes_home()`, which reads the `HERMES_HOME` environment variable. Profile aliases (`coder`, `assistant`, etc.) are wrapper scripts at `~/.local/bin/<name>` that set `HERMES_HOME` before calling `hermes`.

## What is scoped per profile

> **Implementation note**: The exact filenames below (e.g. `MEMORY.md`, `state.db`) reflect Hermes' internal layout. They are accurate against the upstream commit pinned in `manifest.yaml` (`upstream.pinned_commit`). For canonical guarantees, see Hermes' own docs at https://hermes-agent.nousresearch.com/.

| Item | Path inside profile home |
|------|--------------------------|
| Config | `config.yaml` |
| Secrets | `.env` |
| Persona | `SOUL.md` |
| Built-in memory | `MEMORY.md`, `USER.md` |
| Sessions (full chat history, FTS5 searchable) | `state.db` (SQLite) |
| Skills | `skills/` |
| Cron jobs | `cron/` |
| Logs | `logs/` |
| Gateway PID + service state | `gateway/` |
| External memory provider identity (Honcho peer ID, etc.) | provider-scoped |

## What is shared

- The Hermes Python codebase itself (one install).
- Bundled skills sync'd by `hermes update` (auto-updated, but per-profile copies preserve user edits).
- The `~/.local/bin/` directory where aliases live (one alias per profile name; collisions impossible because alias names are unique).

## Isolation guarantees

| Guarantee | How it works |
|-----------|--------------|
| Memory does not leak between profiles | Honcho identity is profile-scoped (v0.5+). Built-in memory files are inside profile home. Cross-pollination requires explicit copy. |
| Sessions are independent | Each profile has its own `state.db`. `hermes sessions list` only shows the active profile's sessions. |
| API keys are isolated | `.env` per profile. `hermes config` writes to active profile's config only. |
| Gateway tokens cannot conflict | Per-profile token lock at gateway start. Same Telegram/Slack/Discord token in two profiles → second gateway refuses to start with explicit error naming the conflicting profile. |
| Each profile's gateway runs as its own service | `<profile> gateway install` creates `hermes-gateway-<profile>` systemd/launchd unit. Independent restart, logs, and lifecycle. |

## Isolation limits (read this carefully)

These are NOT isolated:

1. **Filesystem permissions.** On the default `local` terminal backend, every profile has the same access as your user account. Profile A can read/write Profile B's directory if the agent decides to. Profiles do NOT sandbox file access. To get real filesystem isolation, switch the terminal backend to Docker, Modal, Daytona, or SSH.

2. **Working directory.** A profile does not pin its own `cwd`. Tools start from `terminal.cwd` in `config.yaml` (or the launch directory if `cwd: "."`). To make a profile start in a project folder, set an absolute `terminal.cwd`.

3. **System-level resources.** All profiles share your machine's RAM, CPU, ports, and network. If two profiles both run a gateway, both contribute to system load.

4. **The user account.** Same shell, same env outside `.env` (system-wide variables leak in), same home directory.

If your threat model needs hard isolation, run profiles inside containers or remote backends.

## Profile vs subagent vs session — when to use which

| Tool | Granularity | Use when |
|------|-------------|----------|
| **Profile** | Different agent identity entirely | Different personas, different API key budgets, different gateway channels, different long-term memory |
| **Subagent** | Same profile, isolated execution context | Parallel workstreams within one task, delegating sub-questions to a cheaper model, pipelines with no context cost |
| **Session** | Same profile, separate conversation thread | Topic separation; resume later via `hermes -c` or `hermes --resume <id>` |

Rule of thumb: don't create a new profile if a subagent will do. Profiles add operational overhead (separate `.env`, separate gateway, separate memory to curate).

## Defaults set by this kit

This kit creates 4 profiles. The default `~/.hermes` profile is left untouched — you can keep using it for ad-hoc work, and the 4 named profiles are for specific roles.

## Further reading

- Hermes upstream profile docs: https://hermes-agent.nousresearch.com/docs/user-guide/profiles
- Memory architecture deep dive: https://hermesagents.net/blog/memory-architecture-honcho-and-beyond/
- Subagents: https://hermes-agent.nousresearch.com/docs/user-guide/subagents
