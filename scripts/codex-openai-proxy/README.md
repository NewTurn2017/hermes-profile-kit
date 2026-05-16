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
