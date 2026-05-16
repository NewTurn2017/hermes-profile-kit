# codex-openai-proxy

> **Status (as of kit 3.1.2): opt-in escape hatch.** Hermes already ships a
> native `openai-codex` provider that hits `chatgpt.com/backend-api/codex`
> directly from your local Codex CLI OAuth session — that path is faster
> and needs no proxy. Use this plugin only when the native path doesn't
> work for your host (e.g., shared servers where you can't keep a Codex
> CLI session, or when you want to share one Codex auth across many
> machines via local HTTP). The kit no longer enables this plugin by
> default (`default: false` in `manifest.yaml`).

Local OpenAI-compatible HTTP proxy. Translates `/v1/chat/completions` calls from
Hermes' OpenAI adapter to `codex exec --json -` subprocess calls, reusing your
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

The proxy calls `codex exec --skip-git-repo-check --ephemeral --json -m <model> -`
and pipes the rendered prompt over stdin. Output is parsed as JSONL — events of
type `item.completed` with `item.type == "agent_message"` are concatenated into
the assistant content. Events of type `error` or `turn.failed` surface as HTTP
502.

If a future codex CLI changes any of these contracts, update `_to_codex_exec_invocation`
and `_parse_codex_jsonl_events` in `proxy.py` — the HTTP surface stays the same.

Verify with: `codex exec --help` (look for `--json`, `--ephemeral`, `-m`).

### Verifying against the real codex CLI

The default test suite mocks `subprocess.Popen`. To assert our contract still
holds against the installed codex CLI:

    cd scripts/codex-openai-proxy
    CODEX_PROXY_INTEGRATION=1 uv run pytest tests/test_codex_exec_contract.py -v

Requires `codex` CLI logged in (`codex login`).

## Running tests

```bash
uv run pytest tests/ -v
```
