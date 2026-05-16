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

## Modes (LLM + embedder)

`hpk-memory` runs mem0 in one of three modes depending on env vars set before
the CLI is invoked:

| Mode | When to use | Env to set |
|---|---|---|
| **Proxy** (recommended, zero billing keys) | You have a Codex CLI OAuth session via `codex login` and run `codex-openai-proxy` on `:8765`. | `MEM0_LLM_BASE_URL=http://localhost:8765/v1` plus `MEM0_EMBEDDER_PROVIDER=fastembed` (install: `uv pip install -e ".[local-embedder]"`). |
| **OpenAI default** | You have a real OpenAI billing key (`OPENAI_API_KEY`). | None — leave `MEM0_*` env unset; mem0 uses its built-in OpenAI defaults for both LLM and embedder. |
| **Hybrid** | You want local embeddings but real OpenAI for fact extraction (or vice versa). | Mix and match — e.g. set `MEM0_EMBEDDER_PROVIDER=fastembed` only. |

To verify which mode is active for the current shell:

    uv run hpk-memory doctor

The output's `checks.llm_mode` and `checks.embedder_mode` fields say `proxy` or
`openai-default` (or the embedder provider name).

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

~30+ tests covering paths, isolation, CLI shape, doctor, fallback, and a real mem0 roundtrip (best-effort).

## Limitations (intentional)

- Single-writer per profile (chroma concurrency is not stress-tested).
- No encryption at rest. Filesystem permissions are the trust boundary.
- No automatic backup or migration.
- No hosted-mem0 backend yet (planned: `MEM0_API_KEY` token + config switch).
- Without a working LLM extractor, the `query` fallback uses SQL LIKE (substring match only). Queries that are semantically related but lexically different from the stored text will return empty — the README "Demo" section's `--q "사용자 일정"` queries assume a functional `OPENAI_API_KEY`.
