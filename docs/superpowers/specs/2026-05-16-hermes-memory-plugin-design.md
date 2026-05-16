# Hermes memory plugin design — mem0 as a second per-profile + shared memory layer

| Field | Value |
|---|---|
| Date | 2026-05-16 |
| Status | Draft (pending implementation plan) |
| Owner | genie |
| Related | `2026-05-15-hermes-profile-kit-v2-design.md` (kit baseline), `2026-05-15-seb-profile-design.md` (first integration target), `2026-05-16-fast-install-design.md` (install pattern this reuses) |
| Target version | hermes-profile-kit `3.2.0` (additive minor: new kit-local plugin + opt-in entry for `seb`) |

## 1. Problem

The kit ships one external memory plugin today — `honcho-memory`, registered upstream and enabled by default for `assistant` and `research`. `seb` does not use it, and there is no notion of memory shared across profiles. As the kit grows toward a "main orchestrator + many profiles" model, two gaps surface:

1. **No per-profile persistent memory for `seb`.** seb is the heaviest-state profile (a second-brain controller for a private Obsidian vault) yet relies only on the in-context `memory.built_in` block — facts evaporate when the Slack thread rolls.
2. **No shared memory layer across profiles.** A fact like "user's timezone is Asia/Seoul" has to be repeated to every profile, and there is no mechanism to designate one profile (or the user) as the writer of a shared pool while others read it.

The 2026 agent-memory ecosystem has converged on a 4-axis scope model (`user_id` / `agent_id` / `run_id` / `app_id`) popularized by `mem0`. That model maps cleanly onto hermes-profile-kit's profile concept: `agent_id = <profile>` for isolation, `app_id = "hermes-shared"` for cross-profile sharing. Adopting it as a second, opt-in memory option (alongside `honcho-memory`) gives us the orchestrator-ready substrate without disturbing honcho users.

## 2. Goals and non-goals

**Goals**

1. Add `mem0-memory` as a new kit-local plugin registered in `manifest.yaml`, parallel to `honcho-memory` — never replacing it.
2. Ship a `hpk-memory` CLI exposing the 4-axis scope model behind five subcommands (`add`, `query`, `list`, `share-add`, `share-list`) plus `doctor`. CLI is the single integration surface.
3. Persist data locally (mem0 OSS + SQLite + Chroma) under `~/.hermes/profiles/<profile>/memory/` and `~/.hermes/shared/memory/`. Zero external API keys required.
4. Update `seb`'s SOUL.md with ≤ 8 lines instructing it to invoke the CLI through its existing `shell` tool. No changes to `seb`'s `config.yaml` or to Hermes core.
5. Demonstrate cross-profile isolation + shared-pool read in a 4-line manual scenario captured in the README.
6. Land the plugin as `default: false` on `seb`'s `recommended_plugins` (opt-in), matching the `codex-openai-proxy` precedent.

**Non-goals**

1. Replacing or deprecating `honcho-memory`. mem0 is a second option, not a successor.
2. Modifying the `hpk` core (`src/hpk/*.py`). The existing plugin runner already refuses to auto-install kit-local plugins; we reuse that path.
3. Modifying the upstream `hermes` binary or registering mem0 with `hermes -p <p> memory setup <provider>`. The mem0 plugin lives entirely outside Hermes runtime for this release.
4. Two-way sharing. `seb` (and any non-orchestrator profile) reads from the shared pool but cannot write to it; only the user writes via `hpk-memory share-add`.
5. Hosted mem0 (mem0.ai), Qdrant self-hosting, encrypted-at-rest storage, automatic backup, or store-format migration. All deferred.
6. A real Slack → seb → CLI end-to-end automated test. Slack-stack cost is too high for the PoC value.
7. Defining the "orchestrator profile" itself. This design only opens the slot; the orchestrator design is a separate spec.

**Success criteria**

- A user with `mem0-memory` installed runs:
  ```bash
  hpk-memory share-add  --text "사용자 timezone Asia/Seoul"
  hpk-memory add --profile seb       --text "seb은 매일 09:00에 daily note 생성"
  hpk-memory add --profile assistant --text "오후 회의 선호"
  hpk-memory query --profile seb --q "사용자 일정" --scope all
  ```
  and the final call returns exactly the seb fact + the shared fact, never the assistant fact.
- New plugin tests (`scripts/mem0-memory/tests/`) cover paths, store isolation, CLI shape, doctor, LLM-extractor fallback, and add → query roundtrip — all green in CI without an OpenAI key (LLM extractor monkey-patched in tests).
- Three new hpk e2e tests confirm manifest registration, plugin runner's "install manually" refusal for the kit-local mem0 plugin, and seb's `recommended_plugins` entry with `default: false`.
- `seb`'s SOUL.md, after the update, instructs the model to call `hpk-memory query` only on clear recall intent and `hpk-memory add` only on explicit "기억해줘" intent — confirmed by a short manual Slack-thread walk-through.

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Slack thread (user ↔ seb)                                   │
└─────────────────────────────────────────────────────────────┘
            │
            ▼  (Hermes core, unchanged)
┌─────────────────────────────────────────────────────────────┐
│ seb profile  ──  tools: [file, shell, web_search, web_fetch] │
│   SOUL.md gains a "Memory access" section instructing the    │
│   model to call hpk-memory via the shell tool                │
└─────────────────────────────────────────────────────────────┘
            │ shell tool invocation
            ▼
┌─────────────────────────────────────────────────────────────┐
│ hpk-memory  (kit-local CLI, scripts/mem0-memory/)            │
│   add / query / list / share-add / share-list / doctor       │
│                                                              │
│   ┌──────────────────────────────────────────────────────┐  │
│   │ mem0 client (Python lib, isolated venv)              │  │
│   │   agent_id   = <profile>     (isolation, R/W)        │  │
│   │   app_id     = hermes-shared (sharing, R only here)  │  │
│   │   user_id    = <git email>   (future expansion)      │  │
│   └──────────────────────────────────────────────────────┘  │
│            │                                                 │
│            ▼ persists to                                     │
│   ~/.hermes/profiles/<profile>/memory/                       │
│     ├─ store.sqlite                                          │
│     └─ chroma/                                               │
│   ~/.hermes/shared/memory/                                   │
│     ├─ store.sqlite                                          │
│     └─ chroma/                                               │
└─────────────────────────────────────────────────────────────┘
```

Three boundaries, each independently replaceable:

1. **CLI surface (`hpk-memory ...`)** — the sole external interface. JSON-on-stdout for machine parsing, text mode for humans. All scope semantics are visible as CLI flags.
2. **Storage isolation** — per-profile directory + a sibling shared directory. Filesystem-level separation; even if a mem0 internal scoping bug existed, data would not cross.
3. **Plugin-runner relationship** — `manifest.yaml` entry with `install_path: scripts/mem0-memory` and `upstream_command: null` reuses the existing `PluginExecError("install manually")` path. Zero changes to `src/hpk/plugins.py`.

Substituting mem0 with letta or graphiti later means rewriting only the CLI internals. Promoting this plugin to a Hermes-upstream-registered provider (the `honcho` path) later means wrapping the CLI as a library import — the CLI itself becomes the stable contract.

## 4. Components

### 4.1 `scripts/mem0-memory/` (kit-local plugin package)

```
scripts/mem0-memory/
├─ pyproject.toml          # name=hermes-mem0-memory, deps: mem0ai, click
├─ README.md               # install / usage / troubleshooting / demo
├─ src/mem0_memory/
│   ├─ __init__.py
│   ├─ cli.py              # click entrypoint → hpk-memory
│   ├─ store.py            # mem0 Memory() factory, per-scope
│   ├─ paths.py            # ~/.hermes/profiles/<p>/memory, ~/.hermes/shared/memory
│   └─ output.py           # JSON serialization helpers
└─ tests/
    ├─ test_paths.py
    ├─ test_store.py
    ├─ test_cli.py
    ├─ test_doctor.py
    ├─ test_fallback.py
    └─ test_roundtrip.py
```

Install follows the `codex-openai-proxy` precedent: `cd scripts/mem0-memory && uv venv && uv pip install -e .`. The console script `hpk-memory` is exposed via `pyproject.toml`'s `[project.scripts]`; the user symlinks or PATH-adds the venv's `bin/` directory as documented in the README.

### 4.2 CLI surface (contract)

```bash
hpk-memory add      --profile <p> --text "..." [--meta key=val ...]
hpk-memory query    --profile <p> --q "..." [--scope profile|shared|all] [--limit 5]
hpk-memory list     --profile <p> [--scope profile|shared|all] [--limit 20]
hpk-memory share-add --text "..." [--meta key=val ...]
hpk-memory share-list [--limit 20]
hpk-memory doctor
```

- All outputs default to JSON on stdout. `--text` flag yields a human-readable form.
- `--scope` defaults: `query` and `list` default to `all` (profile + shared, merged); `add` rejects any `--scope` value other than the implicit `profile`.
- `share-add` is a separate subcommand specifically so accidental writes to the shared pool are impossible via the normal `add` path.
- Exit codes: `0` success / `1` user input error / `2` environment or store error / `10` mem0 extractor (LLM) failure / `20` mem0 ImportError.
- Failure JSON shape: `{"ok": false, "code": <int>, "kind": "<machine-readable>", "msg": "...", "hint": "..."}`.

### 4.3 Storage layout

```
~/.hermes/
├─ profiles/
│   └─ <profile>/
│       └─ memory/
│           ├─ store.sqlite
│           └─ chroma/
└─ shared/
    └─ memory/
        ├─ store.sqlite
        └─ chroma/
```

Directories are created on first write with mode 0700 (parent dir). Test override via `HERMES_HOME` environment variable, allowing CI to point at a tmpdir.

### 4.4 `manifest.yaml` changes

```yaml
plugins:
  # ... existing ...
  mem0-memory:
    description: "Local mem0 store for per-profile + shared memory (kit-local, OSS, zero tokens)."
    upstream_command: null
    install_path: scripts/mem0-memory
    verified_in_upstream: false
    docs: scripts/mem0-memory/README.md
```

`profiles.seb.recommended_plugins` adds:

```yaml
- { id: mem0-memory, default: false }
```

`schema_version` stays at `3`. No other profile is touched in this release.

### 4.5 `seb` profile changes (minimal)

- `profiles/seb/SOUL.md`: append a "Memory access" section (~6–8 lines) instructing the model:
  - On clear recall intent → call `hpk-memory query --profile seb --q "..."` via `shell`, use `memories[].text` from the JSON result.
  - On explicit "기억해줘" / "메모해" intent → call `hpk-memory add --profile seb --text "..."`. Never write to shared.
  - On exit code `10` → fallback already saved raw text; treat as success but mention degradation to the user. On exit code `20` → instruct user to run `hpk-memory doctor`.
- `profiles/seb/config.yaml`: **no changes.** The existing `memory.built_in` block stays — mem0 is an additive layer.

### 4.6 `hpk` core changes

**None.** The plugin runner at `src/hpk/plugins.py` already raises `PluginExecError("install manually")` for plugins with `install_path` set and `verified_in_upstream: false`. The mem0 plugin reuses that path verbatim.

## 5. Data flow

### 5.1 Write path (isolated, per-profile)

```
user (Slack): "내 vault root는 /Users/genie/Obsidian/second-brain/second-brain. 기억해줘."
   → seb detects "기억해줘"
   → shell: hpk-memory add --profile seb --text "User's Obsidian vault root is /..."
   → cli → Store(profile="seb").add(text, agent_id="seb", user_id=<git email>)
   → mem0 internal: LLM-extract → "vault_root = /..." → embed → write to chroma/
                    metadata → store.sqlite (agent_id=seb, ts, source)
   → stdout: {"ok": true, "id": "mem_abc123", "stored_facts": 1, "scope": "profile"}
   → seb: "기억했습니다. (mem_abc123)"
```

Invariant: `add` hard-codes `agent_id = <profile>`. A user typo like `--profile foo` writes only to `~/.hermes/profiles/foo/memory/`, never to shared.

### 5.2 Read path (merged: profile + shared)

```
user (Slack): "내 vault 어디였지?"
   → seb detects recall intent
   → shell: hpk-memory query --profile seb --q "vault location" --scope all --limit 5
   → cli runs in parallel:
       ├─ Store(profile="seb").search(q, agent_id="seb")
       └─ Store(shared).search(q, app_id="hermes-shared")
   → merge by score, dedupe by text-similarity (cosine ≥ 0.95 on embeddings)
   → stdout: {
       "ok": true,
       "memories": [
         {"text": "vault_root = /...", "score": 0.91, "scope": "profile",
          "agent_id": "seb", "id": "mem_abc123", "ts": "..."},
         {"text": "사용자 timezone Asia/Seoul", "score": 0.42, "scope": "shared",
          "id": "shm_xyz789", "ts": "..."}
       ]
     }
   → seb: "/Users/genie/Obsidian/second-brain/second-brain 입니다."
```

Each memory carries an explicit `scope` field so seb (and human debuggers) can see where every fact came from.

### 5.3 Shared-pool write (user only)

```
user (terminal, not Slack):
$ hpk-memory share-add --text "Genie의 작업 OS는 macOS Darwin 25.5.0."
{"ok": true, "id": "shm_def456", "scope": "shared"}
```

seb has no SOUL-permitted path to `share-add`. It can technically `shell` the command (the CLI does not reject it the way it rejects `add --scope shared`), but the SOUL forbids it and there is no operational reason to do so. The asymmetry is intentional: `add --scope shared` is CLI-blocked because it is a mistake-class error; `share-add` direct invocation is SOUL-only-blocked because it is the orchestrator's future API — a future orchestrator profile gains `share-add` privileges by SOUL policy, not by CLI changes.

### 5.4 Cross-profile demo (PoC success criterion)

```
hpk-memory share-add --text "사용자 timezone Asia/Seoul"
hpk-memory add --profile seb       --text "seb은 매일 09:00에 daily note 생성"
hpk-memory add --profile assistant --text "오후 회의 선호"

hpk-memory query --profile seb --q "사용자 일정" --scope all
→ {memories: [seb-fact, shared-fact]}        # assistant-fact absent

hpk-memory query --profile assistant --q "사용자 일정" --scope all
→ {memories: [assistant-fact, shared-fact]}  # seb-fact absent
```

### 5.5 Concurrency

- mem0 SQLite is opened in WAL mode (`PRAGMA journal_mode=WAL`) by `store.py` to allow concurrent reads alongside one writer.
- chroma directory concurrency relies on chromadb's internal lock. PoC assumes one writer per profile at a time; documented in README.

## 6. Error handling

The CLI is the single integration surface, so all failures travel through `(exit_code, JSON body)`.

### 6.1 Exit code matrix

| Code | Meaning | Trigger | seb behavior (per SOUL) |
|---:|---|---|---|
| 0 | success | normal | use result |
| 1 | user input error | empty `--q`, unknown `--scope`, `add --scope shared` | ask user to clarify args |
| 2 | environment / store error | dir permission denied, SQLite lock timeout, chroma corruption | one-line "memory temporarily unavailable", proceed without memory |
| 10 | mem0 extractor (LLM) failure | network or OpenAI key missing during fact extraction | report success (raw text already saved as fallback), note degradation |
| 20 | mem0 ImportError | venv missing or package not installed | instruct user to run `hpk-memory doctor` |

Failure JSON shape: `{"ok": false, "code": <int>, "kind": "<machine-readable>", "msg": "...", "hint": "..."}`. Example: `{"ok": false, "code": 2, "kind": "store_locked", "msg": "profile store busy (sqlite WAL lock)", "hint": "retry in 1s"}`.

### 6.2 Specific scenarios

- **mem0 ImportError (exit 20):** CLI's first action is `import mem0` in a try/except. Failure prints the install command from the README. `hpk-memory doctor` runs the same check explicitly so seb can hand the user a single command.
- **Storage directory missing:** CLI auto-creates with `mode=0700`. Permission denied → exit 2, `kind=permission_denied`.
- **SQLite WAL lock contention:** mem0 calls wrapped with a 5-second timeout. Lock conflict → exit 2, `kind=store_locked`, `hint="retry in 1s"`. seb retries once at most (SOUL rule), never loops.
- **chroma index corruption:** detected by `doctor`. Recovery is manual: README documents `tar czf chroma.bak.YYYYMMDD.tgz chroma/` then directory delete + re-init. CLI never auto-repairs (data-loss risk).
- **mem0 LLM extractor failure (exit 10):** mem0 calls an LLM to distill facts. If the call fails (no key, network, rate limit), CLI falls back to writing the raw text into a `raw_facts` table directly in `store.sqlite` and returns exit 10 with `saved_raw=true`. `query` checks `raw_facts` via SQL `LIKE` as a fallback, so "기억해줘" stays honest even with no LLM key configured.
- **Empty query result:** exit 0, `memories: []`. seb's SOUL: do not announce "no memory found" to the user — just answer without memory context.
- **Shared-pool write via `add`:** `add --scope shared` returns exit 1, `kind=shared_write_forbidden`, `hint="use share-add"`. CLI-level guard so the SOUL rule is not the sole barrier.
- **JSON parse failure on seb side:** seb's responsibility. SOUL: "if stdout is not valid JSON or `ok` field absent, proceed without memory and do not surface the error to the user."

### 6.3 Intentional non-features

- **No automatic store migration.** A mem0 major version bump that changes on-disk format triggers a `doctor` warning only — no automatic conversion, to avoid data loss.
- **No automatic backup.** README documents one `tar` command. PoC scope.
- **No encryption-at-rest.** Filesystem permissions (0700) are the trust boundary. Consistent with seb's LOCKED-zone treatment of the disk.
- **No retry/backoff library.** seb's one-shot retry is sufficient at this scale.

## 7. Testing

### 7.1 Layer 1 — `scripts/mem0-memory/tests/` (plugin unit + integration)

Run inside the plugin's own venv: `cd scripts/mem0-memory && uv run pytest`. CI calls this step in addition to the existing `pytest` for `hpk`.

| File | Guarantee |
|---|---|
| `test_paths.py` | `~/.hermes/profiles/<p>/memory` and `~/.hermes/shared/memory` resolution. `HERMES_HOME` env override is respected. |
| `test_store.py` | `Store(profile="seb")` and `Store(shared)` use disjoint chroma paths and sqlite files. Profile-write then shared-search returns empty (isolation). Shared-write then profile-search with `--scope all` returns the fact (merge). |
| `test_cli.py` | click argument parsing. Missing `--profile` → exit 1, `kind=missing_arg`. `add --scope shared` → exit 1, `kind=shared_write_forbidden`. All `--json` outputs are valid JSON with the documented field set. |
| `test_doctor.py` | mem0 import OK + directory present + sqlite healthy → exit 0. Deliberate breakage of each → exit 2 with the right `kind`. |
| `test_fallback.py` | mem0 LLM call mocked to raise → exit 10, `saved_raw=true`. `raw_facts` table populated. Subsequent `query` returns the raw fact via LIKE. |
| `test_roundtrip.py` | One real `add` → `query` cycle. mem0's `llm` config monkey-patched to an echo extractor (no external network). Wall time budget ≤ 30 s. |

Expected ~25 tests total. No external API keys needed in CI.

### 7.2 Layer 2 — `tests/e2e/test_mem0_memory.py` (hpk integration)

Follows the `tests/e2e/test_seb_setup.py` pattern. 3–5 tests:

```python
def test_manifest_registers_mem0_memory_plugin(manifest):
    assert "mem0-memory" in manifest.plugins
    p = manifest.plugins["mem0-memory"]
    assert p.upstream_command is None
    assert p.install_path == "scripts/mem0-memory"

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

Existing 88-test suite grows to ~91.

### 7.3 Layer 3 — manual demo (in README, not automated)

The four-line cross-profile demo from section 5.4. Not automated — Slack-stack cost outweighs PoC value, and the same isolation/merge invariants are already covered deterministically by Layer 1's `test_store.py`.

### 7.4 TDD order (to be carried into the implementation plan)

1. `test_paths.py` → `paths.py`
2. `test_store.py` → `store.py` (scope dirs, mem0 Memory factory)
3. `test_cli.py` → `cli.py` (click commands, JSON output)
4. `test_fallback.py` (extractor-failure path)
5. `test_doctor.py`
6. `test_roundtrip.py` (real mem0 + monkey-patched extractor)
7. Layer 2 hpk e2e
8. `profiles/seb/SOUL.md` "Memory access" section
9. `scripts/mem0-memory/README.md` (install, usage, demo, troubleshooting)
10. Update `manifest.yaml` `plugins:` + `seb.recommended_plugins`

### 7.5 Intentional non-tests

- mem0 library internals — upstream's responsibility.
- chroma concurrency stress — out of PoC scope (single-writer assumption documented).
- Full Slack → seb → CLI e2e — Slack-bot setup overhead too high for the value.

## 8. Open questions / future work (out of scope for this release)

1. **Orchestrator profile.** Who writes to `hermes-shared`? Likely a new "hub" or repurposed `assistant`. Separate spec.
2. **Promotion to Hermes upstream.** Once the CLI contract proves out, propose a `hermes -p <p> memory setup mem0` adapter in upstream Hermes and flip `verified_in_upstream: true`. Would unify with `honcho`'s installation flow.
3. **Hosted mem0 backend.** Optional `MEM0_API_KEY` token + manifest TokenSpec to switch backends without changing the CLI surface.
4. **Per-fact ACLs.** mem0 supports metadata filters — e.g., `meta:private=true` could hide a fact from shared-pool merges even when it lives in shared. Not needed yet.
5. **Memory replay / export.** `hpk-memory export --profile seb > seb-facts.jsonl` for backup, audit, or migration to a future provider. Trivial to add when needed.

## 9. Rollout

- This is a `3.2.0` minor release (additive: new plugin, new opt-in `recommended_plugins` entry, SOUL.md text change).
- Existing users see no behavior change unless they explicitly install the plugin (`default: false` on seb).
- CHANGELOG entry under `[3.2.0] — Added`:
  - `mem0-memory` kit-local plugin (per-profile + shared, OSS, zero tokens).
  - `hpk-memory` CLI (add/query/list/share-add/share-list/doctor).
  - seb SOUL gains "Memory access" section.
- README's "Plugins" table gains a `mem0-memory` row. seb's profile README points to the demo in `scripts/mem0-memory/README.md`.
