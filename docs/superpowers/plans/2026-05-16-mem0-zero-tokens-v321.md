# mem0 zero-tokens (v3.2.1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver on the "zero external billing keys" promise of v3.2.0 mem0-memory by (a) migrating `codex-openai-proxy` to today's `codex exec` CLI so its OAuth path actually works, (b) wiring `mem0-memory` to honor env vars that route its LLM through that proxy and its embedder through a local ONNX model, and (c) closing the silent-extraction-failure hole in `Store.add` so raw fallback always fires.

**Architecture:** Three independent deliverables released as one version (v3.2.1). The proxy and the kit stay loosely coupled — the proxy publishes an OpenAI-compatible `/v1/chat/completions` surface (no embeddings), and the kit picks the LLM/embedder providers from env. Default behavior (no env set) is unchanged from v3.2.0 so existing users with `OPENAI_API_KEY` keep working.

**Tech Stack:** Python 3.11+, FastAPI/uvicorn (proxy), `mem0ai` v2, `fastembed` (new optional extra), `pytest`. New external dependency: `fastembed>=0.8` behind a `[local-embedder]` extra.

**Spec:** Builds on `docs/superpowers/specs/2026-05-16-hermes-memory-plugin-design.md` (commit `0a079f1`). No new spec document — the deltas vs. v3.2.0 are captured by this plan.

**PoC evidence:** `/tmp/mem0_codex_poc.py` (session 2026-05-16) confirmed the mem0 + fastembed + chroma path works end-to-end and that mem0's OpenAI LLM provider accepts `openai_base_url` correctly. It also surfaced the broken proxy + silent-fail issues this plan fixes.

---

## File structure

**Created:**
- `scripts/codex-openai-proxy/tests/test_codex_exec_contract.py` — gated integration test that runs real `codex exec` to pin our CLI assumptions
- `scripts/mem0-memory/tests/test_store_env_config.py` — env-driven `Store.config()` tests
- `scripts/mem0-memory/tests/test_store_silent_fallback.py` — silent-extraction-failure → raw fallback test

**Modified:**
- `scripts/codex-openai-proxy/proxy.py` — replace `_to_responses_payload`/`_extract_content` with `_to_codex_exec_invocation`/`_parse_codex_jsonl_events`; rewrite chat completions route to call `codex exec --json -`
- `scripts/codex-openai-proxy/tests/test_proxy.py` — update mocks for new subprocess invocation
- `scripts/codex-openai-proxy/pyproject.toml` — version `0.1.0` → `0.2.0`
- `scripts/codex-openai-proxy/README.md` — update CLI interface note + add "Verifying against real codex CLI" section
- `scripts/mem0-memory/src/mem0_memory/store.py` — env-driven `Store.config()`; silent-extraction-failure detection in `Store.add`
- `scripts/mem0-memory/src/mem0_memory/cli.py` — `doctor` reports active LLM/embedder mode
- `scripts/mem0-memory/tests/test_store.py` — adapt `add` test to new return shape (`extracted` field)
- `scripts/mem0-memory/tests/conftest.py` — add `silent_fail_memory_factory` fixture (FakeMemory variant that returns `{"results": []}`)
- `scripts/mem0-memory/tests/test_doctor.py` — assert doctor surfaces mode
- `scripts/mem0-memory/pyproject.toml` — version `0.1.0` → `0.2.0`; add `[project.optional-dependencies] local-embedder = ["fastembed>=0.8"]`
- `scripts/mem0-memory/README.md` — new "Modes" section (proxy / OpenAI / hybrid); update install instructions
- `profiles/seb/SOUL.md` — add a 1-line note about MEM0_LLM_BASE_URL auto-routing through codex-openai-proxy
- `CHANGELOG.md` — add `[3.2.1]` entry
- `pyproject.toml` (root) — version `3.2.0` → `3.2.1`

**Not touched:** `src/hpk/*.py`, `manifest.yaml` (the manifest already exposes both plugins; flipping defaults is out of scope), other profiles, any Hermes upstream code.

---

## Decided contracts (cross-task)

### codex exec invocation contract

The proxy calls:

```
codex exec --skip-git-repo-check --ephemeral --json -m <model> -
```

with the rendered prompt on stdin. Output is **JSONL** with one event per line. Parse rule: collect all events where `event["type"] == "item.completed"` AND `event["item"]["type"] == "agent_message"`, concatenate `event["item"]["text"]` in order, and that string is the assistant content. Any event of type `error` or `turn.failed` → return a 502 with the event's `message` (or `error.message`) field.

### Message rendering (Chat Completions → codex prompt string)

```python
def render_prompt(messages: list[dict]) -> str:
    parts: list[str] = []
    for msg in messages:
        role = msg["role"]
        content = _flatten_content(msg.get("content", ""))
        if role == "system":
            parts.append(f"[system]\n{content}")
        elif role == "user":
            parts.append(f"[user]\n{content}")
        elif role == "assistant":
            parts.append(f"[assistant]\n{content}")
    return "\n\n".join(parts)
```

`_flatten_content` collapses multi-part content (`[{type:"text", text:"..."}, ...]`) into a single string by taking text parts only.

### Unsupported request fields

mem0 v2 sends `response_format={"type":"json_object"}` for fact extraction. `codex exec` has no equivalent flag. The proxy **drops** `response_format` and `tools` silently and logs a `logger.debug` line so it's visible in logs but doesn't fail the request. mem0's prompts already instruct JSON output, so dropping `response_format` is benign in practice.

### Store.config() env contract

`Store.config()` reads these env vars (all optional):

| Env var | Effect when set |
|---|---|
| `MEM0_LLM_BASE_URL` | Inject `llm: {provider: openai, config: {openai_base_url: <value>, ...}}` |
| `MEM0_LLM_API_KEY` | Sets `llm.config.api_key` (default: `"sk-mem0-local-dummy"`) |
| `MEM0_LLM_MODEL` | Sets `llm.config.model` (default: `"gpt-5.5"`) |
| `MEM0_EMBEDDER_PROVIDER` | Inject `embedder: {provider: <value>, config: {...}}` |
| `MEM0_EMBEDDER_MODEL` | Sets `embedder.config.model` |

If no env is set, the `llm` and `embedder` blocks are omitted entirely so mem0 falls back to its built-in OpenAI defaults — preserving backward compatibility with v3.2.0 users who had `OPENAI_API_KEY` set.

### Store.add return shape (new field)

```python
{"raw_result": <mem0 raw>, "scope": "profile"|"shared", "extracted": bool, "raw_id": int | None}
```

`extracted=True` when mem0 returned at least one non-empty `results` entry. `extracted=False` and `raw_id` set when we fell back to `raw_facts` (either because mem0 raised, or because it returned empty results for non-empty input text).

---

## Phase 1 — codex-openai-proxy migration to `codex exec`

### Task 1: Pin the current `codex exec` CLI surface with a gated integration test

**Files:**
- Create: `scripts/codex-openai-proxy/tests/test_codex_exec_contract.py`

- [ ] **Step 1: Write the integration test**

```python
"""Pins the codex CLI surface we depend on. Gated by env so CI doesn't need codex."""
from __future__ import annotations

import json
import os
import subprocess

import pytest

INTEGRATION = os.environ.get("CODEX_PROXY_INTEGRATION") == "1"
pytestmark = pytest.mark.skipif(not INTEGRATION, reason="set CODEX_PROXY_INTEGRATION=1 to run")


def test_codex_exec_returns_agent_message_event():
    """`codex exec ... --json -` must emit at least one item.completed with type=agent_message."""
    proc = subprocess.run(
        ["codex", "exec", "--skip-git-repo-check", "--ephemeral", "--json", "-"],
        input=b"reply with exactly the word OK and nothing else",
        capture_output=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr.decode(errors="replace")
    events = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    agent_msgs = [
        e for e in events
        if e.get("type") == "item.completed" and e.get("item", {}).get("type") == "agent_message"
    ]
    assert agent_msgs, f"no agent_message events in: {events}"
    text = "".join(e["item"]["text"] for e in agent_msgs)
    assert text.strip(), "agent_message text is empty"


def test_codex_exec_accepts_model_flag():
    """`-m gpt-5.5` must not fail with unknown-arg even though codex may route it internally."""
    proc = subprocess.run(
        ["codex", "exec", "--skip-git-repo-check", "--ephemeral", "--json", "-m", "gpt-5.5", "-"],
        input=b"hi",
        capture_output=True,
        timeout=120,
    )
    # Allow non-zero only if it's a model-not-available error from the API, not arg-parsing.
    stderr = proc.stderr.decode(errors="replace")
    assert "unexpected argument" not in stderr, stderr
```

- [ ] **Step 2: Run with integration env to confirm it passes against today's CLI**

Run: `cd scripts/codex-openai-proxy && CODEX_PROXY_INTEGRATION=1 uv run pytest tests/test_codex_exec_contract.py -v`
Expected: 2 passed (assumes `codex auth status` is green).

- [ ] **Step 3: Confirm default test run skips it**

Run: `cd scripts/codex-openai-proxy && uv run pytest tests/test_codex_exec_contract.py -v`
Expected: 2 skipped.

- [ ] **Step 4: Commit**

```bash
git add scripts/codex-openai-proxy/tests/test_codex_exec_contract.py
git commit -m "test(codex-openai-proxy): pin codex exec --json contract with gated integration test"
```

---

### Task 2: Add unit tests for new translation helpers (TDD red)

**Files:**
- Modify: `scripts/codex-openai-proxy/tests/test_proxy.py`

- [ ] **Step 1: Append the new unit tests to `test_proxy.py`**

```python
# ── Translation helpers: _to_codex_exec_invocation ────────────────────────────

def test_to_codex_exec_invocation_single_user_message():
    from proxy import _to_codex_exec_invocation
    args, stdin = _to_codex_exec_invocation({
        "model": "gpt-5.5",
        "messages": [{"role": "user", "content": "hello"}],
    })
    assert args == ["--skip-git-repo-check", "--ephemeral", "--json", "-m", "gpt-5.5", "-"]
    assert stdin == "[user]\nhello"


def test_to_codex_exec_invocation_system_plus_user():
    from proxy import _to_codex_exec_invocation
    _, stdin = _to_codex_exec_invocation({
        "model": "gpt-5.5",
        "messages": [
            {"role": "system", "content": "Respond as JSON."},
            {"role": "user", "content": "extract facts"},
        ],
    })
    assert stdin == "[system]\nRespond as JSON.\n\n[user]\nextract facts"


def test_to_codex_exec_invocation_strips_response_format_and_tools():
    """response_format / tools have no codex exec equivalent — drop them silently."""
    from proxy import _to_codex_exec_invocation
    args, stdin = _to_codex_exec_invocation({
        "model": "gpt-5.5",
        "messages": [{"role": "user", "content": "x"}],
        "response_format": {"type": "json_object"},
        "tools": [{"type": "function", "function": {"name": "f"}}],
    })
    # Just verify no exception; payload is the same as without those fields.
    assert "-m" in args and "gpt-5.5" in args


def test_to_codex_exec_invocation_flattens_multipart_content():
    from proxy import _to_codex_exec_invocation
    _, stdin = _to_codex_exec_invocation({
        "model": "gpt-5.5",
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": "part A"},
            {"type": "text", "text": "part B"},
        ]}],
    })
    assert stdin == "[user]\npart A part B"


# ── Parser: _parse_codex_jsonl_events ─────────────────────────────────────────

def test_parse_codex_jsonl_events_extracts_agent_text():
    from proxy import _parse_codex_jsonl_events
    stdout = b'\n'.join([
        b'{"type":"thread.started","thread_id":"x"}',
        b'{"type":"turn.started"}',
        b'{"type":"item.completed","item":{"id":"i0","type":"agent_message","text":"hello world"}}',
        b'{"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":2}}',
    ])
    text, error = _parse_codex_jsonl_events(stdout)
    assert text == "hello world"
    assert error is None


def test_parse_codex_jsonl_events_concatenates_multiple_messages():
    from proxy import _parse_codex_jsonl_events
    stdout = b'\n'.join([
        b'{"type":"item.completed","item":{"id":"a","type":"agent_message","text":"first."}}',
        b'{"type":"item.completed","item":{"id":"b","type":"agent_message","text":" second."}}',
    ])
    text, error = _parse_codex_jsonl_events(stdout)
    assert text == "first. second."
    assert error is None


def test_parse_codex_jsonl_events_surfaces_error_event():
    from proxy import _parse_codex_jsonl_events
    stdout = b'\n'.join([
        b'{"type":"thread.started"}',
        b'{"type":"error","message":"boom"}',
    ])
    text, error = _parse_codex_jsonl_events(stdout)
    assert text == ""
    assert "boom" in error


def test_parse_codex_jsonl_events_surfaces_turn_failed():
    from proxy import _parse_codex_jsonl_events
    stdout = b'{"type":"turn.failed","error":{"message":"rate limited"}}\n'
    text, error = _parse_codex_jsonl_events(stdout)
    assert error is not None
    assert "rate limited" in error


def test_parse_codex_jsonl_events_ignores_malformed_lines():
    from proxy import _parse_codex_jsonl_events
    stdout = b'\n'.join([
        b'not json at all',
        b'{"type":"item.completed","item":{"id":"a","type":"agent_message","text":"ok"}}',
        b'',
    ])
    text, error = _parse_codex_jsonl_events(stdout)
    assert text == "ok"
    assert error is None
```

- [ ] **Step 2: Run to confirm red**

Run: `cd scripts/codex-openai-proxy && uv run pytest tests/test_proxy.py -v -k "codex_exec or codex_jsonl_events"`
Expected: All new tests FAIL (ImportError: `_to_codex_exec_invocation`/`_parse_codex_jsonl_events` not defined).

- [ ] **Step 3: Commit**

```bash
git add scripts/codex-openai-proxy/tests/test_proxy.py
git commit -m "test(codex-openai-proxy): red — unit tests for codex exec translation + JSONL parser"
```

---

### Task 3: Implement `_to_codex_exec_invocation` and `_parse_codex_jsonl_events`

**Files:**
- Modify: `scripts/codex-openai-proxy/proxy.py`

- [ ] **Step 1: Replace the old translation helpers in `proxy.py`**

In `scripts/codex-openai-proxy/proxy.py`, replace the block from `# ── Translation helpers ─` down to (and including) `_is_auth_error` with:

```python
# ── Translation helpers ────────────────────────────────────────────────────────

import logging  # add near the top with other imports if not already present

logger = logging.getLogger("codex_openai_proxy")


def _flatten_content(content) -> str:
    """Collapse possibly-multipart content into a single string of text parts."""
    if isinstance(content, list):
        return " ".join(part.get("text", "") for part in content if part.get("type") == "text")
    return content or ""


def _render_prompt(messages: list[dict]) -> str:
    parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "user")
        text = _flatten_content(msg.get("content", ""))
        if role in {"system", "user", "assistant"}:
            parts.append(f"[{role}]\n{text}")
    return "\n\n".join(parts)


def _to_codex_exec_invocation(body: dict) -> tuple[list[str], str]:
    """Convert a Chat Completions request to (argv_tail, stdin_str) for `codex exec`.

    Returns the argv *after* `codex exec` and the stdin payload. Drops
    response_format and tools silently (codex CLI has no equivalent) — mem0's
    own system prompts already instruct JSON output, so the drop is benign.
    """
    if body.get("response_format") or body.get("tools"):
        logger.debug("proxy: dropping unsupported fields (response_format / tools)")
    model = body.get("model", MODELS[0])
    args = ["--skip-git-repo-check", "--ephemeral", "--json", "-m", model, "-"]
    stdin = _render_prompt(body.get("messages", []))
    return args, stdin


def _parse_codex_jsonl_events(stdout: bytes) -> tuple[str, str | None]:
    """Parse `codex exec --json` output. Returns (assistant_text, error_or_None)."""
    text_parts: list[str] = []
    error: str | None = None
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue  # ignore malformed lines (e.g., leading banner text)
        etype = event.get("type")
        if etype == "item.completed":
            item = event.get("item") or {}
            if item.get("type") == "agent_message":
                text_parts.append(item.get("text", ""))
        elif etype == "error":
            error = event.get("message") or json.dumps(event)
        elif etype == "turn.failed":
            err = event.get("error") or {}
            error = err.get("message") or json.dumps(event)
    return "".join(text_parts), error


def _is_auth_error(stderr: bytes) -> bool:
    text = stderr.decode(errors="replace").lower()
    return "auth" in text or "login" in text or "not authenticated" in text
```

Also remove the now-dead `_to_responses_payload` and `_extract_content` functions if they remain.

- [ ] **Step 2: Run unit tests to verify green**

Run: `cd scripts/codex-openai-proxy && uv run pytest tests/test_proxy.py -v -k "codex_exec or codex_jsonl_events"`
Expected: All Task 2 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add scripts/codex-openai-proxy/proxy.py
git commit -m "feat(codex-openai-proxy): translate to codex exec invocation + parse JSONL events"
```

---

### Task 4: Rewrite the `/v1/chat/completions` route to call `codex exec`

**Files:**
- Modify: `scripts/codex-openai-proxy/proxy.py` (route + `_stream`)
- Modify: `scripts/codex-openai-proxy/tests/test_proxy.py` (update mocks)

- [ ] **Step 1: Replace the chat_completions and _stream functions in proxy.py**

```python
@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    model: str = body.get("model", MODELS[0])
    stream: bool = body.get("stream", False)
    args, stdin = _to_codex_exec_invocation(body)
    stdin_bytes = stdin.encode()

    try:
        proc = subprocess.Popen(
            ["codex", "exec", *args],
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
        ) from None

    if stream:
        return StreamingResponse(
            _stream(proc, stdin_bytes, model),
            media_type="text/event-stream",
        )

    stdout, stderr = proc.communicate(stdin_bytes)
    if proc.returncode != 0:
        if _is_auth_error(stderr):
            raise HTTPException(
                502,
                detail={
                    "error": {"message": "Run `codex login` first", "type": "codex_auth_required"}
                },
            )
        raise HTTPException(
            502,
            detail={
                "error": {
                    "message": stderr.decode(errors="replace").strip()
                              or "codex exec exited non-zero with no stderr",
                    "type": "codex_error",
                }
            },
        )

    content, error = _parse_codex_jsonl_events(stdout)
    if error:
        raise HTTPException(
            502, detail={"error": {"message": error, "type": "codex_error"}}
        )

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
    """Wait for codex exec to finish, then emit OpenAI SSE chunks."""
    loop = asyncio.get_running_loop()
    stdout, stderr = await loop.run_in_executor(None, proc.communicate, stdin_data)

    if proc.returncode != 0:
        error_text = (
            "Run `codex login` first" if _is_auth_error(stderr)
            else stderr.decode(errors="replace").strip() or "codex exec exited non-zero"
        )
        yield f"data: {json.dumps({'error': {'message': error_text, 'type': 'codex_error'}})}\n\n"
        yield "data: [DONE]\n\n"
        return

    content, error = _parse_codex_jsonl_events(stdout)
    if error:
        yield f"data: {json.dumps({'error': {'message': error, 'type': 'codex_error'}})}\n\n"
        yield "data: [DONE]\n\n"
        return

    chunk = json.dumps({
        "id": "chatcmpl-codex",
        "object": "chat.completion.chunk",
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant", "content": content},
                "finish_reason": None,
            }
        ],
    })
    yield f"data: {chunk}\n\n"

    stop = json.dumps({
        "id": "chatcmpl-codex",
        "object": "chat.completion.chunk",
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    })
    yield f"data: {stop}\n\n"
    yield "data: [DONE]\n\n"
```

- [ ] **Step 2: Update the existing `_fake_popen` mock in `tests/test_proxy.py` to emit JSONL events**

Replace the existing `_fake_popen` helper with:

```python
def _fake_popen(agent_text: str = "Hello world", returncode: int = 0, stderr: bytes = b""):
    """Mock Popen returning codex-exec-style JSONL stdout."""
    mock = MagicMock()
    jsonl = b"\n".join([
        b'{"type":"thread.started","thread_id":"x"}',
        b'{"type":"turn.started"}',
        json.dumps({
            "type": "item.completed",
            "item": {"id": "i0", "type": "agent_message", "text": agent_text},
        }).encode(),
        b'{"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":2}}',
    ])
    mock.communicate.return_value = (jsonl, stderr)
    mock.returncode = returncode
    return mock
```

- [ ] **Step 3: Add a new test verifying the subprocess argv is `codex exec …`**

In `tests/test_proxy.py`:

```python
def test_chat_completions_invokes_codex_exec(client):
    captured: dict = {}

    def fake_popen_factory(cmd, **kwargs):
        captured["cmd"] = cmd
        return _fake_popen("ok")

    with patch("subprocess.Popen", side_effect=fake_popen_factory):
        r = client.post(
            "/v1/chat/completions",
            json={"model": "gpt-5.5", "messages": [{"role": "user", "content": "hi"}]},
        )
    assert r.status_code == 200
    assert captured["cmd"][:2] == ["codex", "exec"]
    assert "--json" in captured["cmd"]
    assert "-m" in captured["cmd"] and "gpt-5.5" in captured["cmd"]
```

- [ ] **Step 4: Run full proxy test suite**

Run: `cd scripts/codex-openai-proxy && uv run pytest tests/test_proxy.py -v`
Expected: All tests PASS (including all pre-existing tests, since the mock signature is compatible).

- [ ] **Step 5: Commit**

```bash
git add scripts/codex-openai-proxy/proxy.py scripts/codex-openai-proxy/tests/test_proxy.py
git commit -m "feat(codex-openai-proxy): route /v1/chat/completions through codex exec --json"
```

---

### Task 5: Proxy version bump + README update + manual end-to-end verification

**Files:**
- Modify: `scripts/codex-openai-proxy/pyproject.toml`
- Modify: `scripts/codex-openai-proxy/README.md`

- [ ] **Step 1: Bump proxy version**

In `scripts/codex-openai-proxy/pyproject.toml` change:

```toml
version = "0.1.0"
```

to:

```toml
version = "0.2.0"
```

- [ ] **Step 2: Update README "CLI interface note" section**

Replace the existing `## CLI interface note` section in `scripts/codex-openai-proxy/README.md` with:

```markdown
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

Requires `codex auth status` to be green.
```

- [ ] **Step 3: Run the full proxy test suite one more time + boot test**

```bash
cd scripts/codex-openai-proxy
uv run pytest -v
# Optional manual smoke test:
uv run uvicorn proxy:app --port 8765 &
sleep 2
curl -s http://localhost:8765/v1/chat/completions -H 'content-type: application/json' \
  -d '{"model":"gpt-5.5","messages":[{"role":"user","content":"reply OK"}]}' | head
kill %1
```

Expected: all tests pass; manual curl returns a `chat.completion` JSON with non-empty content.

- [ ] **Step 4: Commit**

```bash
git add scripts/codex-openai-proxy/pyproject.toml scripts/codex-openai-proxy/README.md
git commit -m "chore(codex-openai-proxy): bump to 0.2.0 + README aligned with codex exec migration"
```

---

## Phase 2 — Store silent-fail fix

### Task 6: Detect mem0's silent extraction failure → save to `raw_facts`

**Files:**
- Modify: `scripts/mem0-memory/tests/conftest.py`
- Create: `scripts/mem0-memory/tests/test_store_silent_fallback.py`
- Modify: `scripts/mem0-memory/src/mem0_memory/store.py:95-107`
- Modify: `scripts/mem0-memory/tests/test_store.py` (adapt 1 existing assertion)

- [ ] **Step 1: Add a `silent_fail_memory_factory` fixture in `conftest.py`**

Append to `scripts/mem0-memory/tests/conftest.py`:

```python
class SilentlyFailingMemory(FakeMemory):
    """Mimics mem0 v2 behavior when LLM extraction fails: returns empty results,
    does NOT raise."""

    def add(self, messages: str, **kwargs: Any) -> dict[str, Any]:
        return {"results": []}


@pytest.fixture
def silent_fail_memory_factory():
    instances: list[SilentlyFailingMemory] = []

    def factory(config: dict[str, Any]) -> SilentlyFailingMemory:
        m = SilentlyFailingMemory(config)
        instances.append(m)
        return m

    factory.instances = instances  # type: ignore[attr-defined]
    return factory
```

- [ ] **Step 2: Write the failing fallback test**

Create `scripts/mem0-memory/tests/test_store_silent_fallback.py`:

```python
"""Silent-extraction-failure fallback: when mem0 returns no facts for non-empty input,
Store.add must persist the raw text to `raw_facts` so the original message is recoverable."""
from __future__ import annotations

import sqlite3

from mem0_memory.store import Store


def test_silent_failure_falls_back_to_raw_facts(hermes_home, silent_fail_memory_factory):
    s = Store(profile="seb", memory_factory=silent_fail_memory_factory)
    result = s.add("seb keeps the vault at /opt/vault")

    assert result["extracted"] is False
    assert result["raw_id"] is not None

    con = sqlite3.connect(s.dir / "store.sqlite")
    try:
        rows = con.execute("SELECT text FROM raw_facts").fetchall()
    finally:
        con.close()
    assert rows == [("seb keeps the vault at /opt/vault",)]


def test_silent_failure_search_finds_raw_fact(hermes_home, silent_fail_memory_factory):
    s = Store(profile="seb", memory_factory=silent_fail_memory_factory)
    s.add("vault path is /opt/vault")
    hits = s.search("vault", limit=5)
    assert any(h.get("raw") for h in hits)
    assert any("/opt/vault" in h["text"] for h in hits)


def test_successful_extraction_does_not_save_raw(hermes_home, fake_memory_factory):
    """When extraction works, no raw fallback row should be created."""
    s = Store(profile="seb", memory_factory=fake_memory_factory)
    result = s.add("seb likes filesystem isolation")

    assert result["extracted"] is True
    assert result["raw_id"] is None

    con = sqlite3.connect(s.dir / "store.sqlite")
    try:
        rows = con.execute("SELECT COUNT(*) FROM raw_facts").fetchone()
    finally:
        con.close()
    assert rows == (0,)
```

- [ ] **Step 3: Run to confirm red**

Run: `cd scripts/mem0-memory && uv run pytest tests/test_store_silent_fallback.py -v`
Expected: 3 failures (`extracted`/`raw_id` keys don't exist on the return dict).

- [ ] **Step 4: Update `Store.add` to detect empty extraction and fall back**

Replace the `add` method in `scripts/mem0-memory/src/mem0_memory/store.py` (lines 95-107) with:

```python
def add(self, text: str, *, user_id: str | None = None, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    # mem0 v2 Memory.add takes scope IDs as top-level kwargs.
    kwargs: dict[str, Any] = dict(self.scope_kwargs)
    if user_id is not None:
        kwargs["user_id"] = user_id
    if meta:
        kwargs["metadata"] = meta
    try:
        result = self.mem.add(text, **kwargs)
    except Exception as exc:
        # Hard failure (network, auth, etc.): persist raw + bubble up.
        self._save_raw(text, meta)
        raise ExtractorError(str(exc)) from exc

    # mem0 v2 swallows LLM extraction errors and returns empty results. Detect
    # that case so the original text is still recoverable via raw_facts.
    items = result.get("results", []) if isinstance(result, dict) else result
    if not items and text.strip():
        raw_id = self._save_raw(text, meta)
        return {
            "raw_result": result,
            "scope": self.scope_name,
            "extracted": False,
            "raw_id": raw_id,
        }
    return {
        "raw_result": result,
        "scope": self.scope_name,
        "extracted": True,
        "raw_id": None,
    }
```

- [ ] **Step 5: Adapt the existing `test_add_passes_scope_kwargs_to_mem0` test**

In `scripts/mem0-memory/tests/test_store.py`, no signature change is required (the test only inspects `fake.added`, not the return shape). But if any other existing test asserted the old return shape, update it. Run:

```bash
cd scripts/mem0-memory && uv run pytest tests/test_store.py -v
```

Expected: all existing tests still pass.

- [ ] **Step 6: Run the new fallback tests**

Run: `cd scripts/mem0-memory && uv run pytest tests/test_store_silent_fallback.py -v`
Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add scripts/mem0-memory/src/mem0_memory/store.py \
        scripts/mem0-memory/tests/conftest.py \
        scripts/mem0-memory/tests/test_store_silent_fallback.py
git commit -m "fix(mem0-memory): silent extraction failure falls back to raw_facts"
```

---

## Phase 3 — Store env injection (3 modes)

### Task 7: `Store.config()` injects `llm` block from `MEM0_LLM_*` env

**Files:**
- Create: `scripts/mem0-memory/tests/test_store_env_config.py`
- Modify: `scripts/mem0-memory/src/mem0_memory/store.py` (`config()` method)

- [ ] **Step 1: Write the failing test**

Create `scripts/mem0-memory/tests/test_store_env_config.py`:

```python
"""Store.config() honors MEM0_* env vars to enable proxy / OpenAI / fastembed modes
without code changes."""
from __future__ import annotations

import pytest

from mem0_memory.store import Store


def test_no_env_means_no_llm_or_embedder_blocks(hermes_home, monkeypatch, fake_memory_factory):
    """v3.2.0 backward compat: with no env, mem0 keeps its built-in OpenAI defaults."""
    for k in ("MEM0_LLM_BASE_URL", "MEM0_LLM_API_KEY", "MEM0_LLM_MODEL",
              "MEM0_EMBEDDER_PROVIDER", "MEM0_EMBEDDER_MODEL"):
        monkeypatch.delenv(k, raising=False)
    cfg = Store(profile="seb", memory_factory=fake_memory_factory).config()
    assert "llm" not in cfg
    assert "embedder" not in cfg


def test_llm_base_url_env_injects_proxy_block(hermes_home, monkeypatch, fake_memory_factory):
    monkeypatch.setenv("MEM0_LLM_BASE_URL", "http://localhost:8765/v1")
    cfg = Store(profile="seb", memory_factory=fake_memory_factory).config()
    assert cfg["llm"]["provider"] == "openai"
    assert cfg["llm"]["config"]["openai_base_url"] == "http://localhost:8765/v1"
    # api_key + model fall back to safe defaults
    assert cfg["llm"]["config"]["api_key"] == "sk-mem0-local-dummy"
    assert cfg["llm"]["config"]["model"] == "gpt-5.5"


def test_llm_api_key_and_model_env_override(hermes_home, monkeypatch, fake_memory_factory):
    monkeypatch.setenv("MEM0_LLM_BASE_URL", "http://localhost:8765/v1")
    monkeypatch.setenv("MEM0_LLM_API_KEY", "sk-real")
    monkeypatch.setenv("MEM0_LLM_MODEL", "gpt-5.4-mini")
    cfg = Store(profile="seb", memory_factory=fake_memory_factory).config()
    assert cfg["llm"]["config"]["api_key"] == "sk-real"
    assert cfg["llm"]["config"]["model"] == "gpt-5.4-mini"
```

- [ ] **Step 2: Run to confirm red**

Run: `cd scripts/mem0-memory && uv run pytest tests/test_store_env_config.py -v -k llm`
Expected: 2 failures (assertion errors on `cfg["llm"]`).

- [ ] **Step 3: Update `Store.config()` to read LLM env**

Modify `scripts/mem0-memory/src/mem0_memory/store.py` — at the top of the file add:

```python
import os
```

(near the other `import` statements; skip if already present.)

Then replace the existing `config()` method body with:

```python
def config(self) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "vector_store": {
            "provider": "chroma",
            "config": {
                "collection_name": self._collection_name,
                "path": str(self.dir / "chroma"),
            },
        },
        "history_db_path": str(self.dir / "store.sqlite"),
    }

    llm_base_url = os.environ.get("MEM0_LLM_BASE_URL")
    if llm_base_url:
        cfg["llm"] = {
            "provider": "openai",
            "config": {
                "model": os.environ.get("MEM0_LLM_MODEL", "gpt-5.5"),
                "openai_base_url": llm_base_url,
                "api_key": os.environ.get("MEM0_LLM_API_KEY", "sk-mem0-local-dummy"),
            },
        }

    return cfg
```

- [ ] **Step 4: Verify Task 7 tests pass**

Run: `cd scripts/mem0-memory && uv run pytest tests/test_store_env_config.py -v -k llm`
Expected: 2 passed.

- [ ] **Step 5: Verify pre-existing tests still pass**

Run: `cd scripts/mem0-memory && uv run pytest tests/test_store.py -v`
Expected: all pass (the no-env case keeps the same config shape).

- [ ] **Step 6: Commit**

```bash
git add scripts/mem0-memory/src/mem0_memory/store.py \
        scripts/mem0-memory/tests/test_store_env_config.py
git commit -m "feat(mem0-memory): Store.config injects llm block from MEM0_LLM_* env"
```

---

### Task 8: `Store.config()` injects `embedder` block from `MEM0_EMBEDDER_*` env

**Files:**
- Modify: `scripts/mem0-memory/tests/test_store_env_config.py` (add tests)
- Modify: `scripts/mem0-memory/src/mem0_memory/store.py` (extend `config()`)

- [ ] **Step 1: Append the embedder tests to `test_store_env_config.py`**

```python
def test_embedder_provider_env_injects_block(hermes_home, monkeypatch, fake_memory_factory):
    monkeypatch.setenv("MEM0_EMBEDDER_PROVIDER", "fastembed")
    monkeypatch.setenv("MEM0_EMBEDDER_MODEL", "BAAI/bge-small-en-v1.5")
    cfg = Store(profile="seb", memory_factory=fake_memory_factory).config()
    assert cfg["embedder"]["provider"] == "fastembed"
    assert cfg["embedder"]["config"]["model"] == "BAAI/bge-small-en-v1.5"


def test_embedder_provider_env_without_model(hermes_home, monkeypatch, fake_memory_factory):
    """If only provider is set, leave model unset so mem0 picks its provider default."""
    monkeypatch.delenv("MEM0_EMBEDDER_MODEL", raising=False)
    monkeypatch.setenv("MEM0_EMBEDDER_PROVIDER", "huggingface")
    cfg = Store(profile="seb", memory_factory=fake_memory_factory).config()
    assert cfg["embedder"]["provider"] == "huggingface"
    assert "model" not in cfg["embedder"]["config"]
```

- [ ] **Step 2: Run to confirm red**

Run: `cd scripts/mem0-memory && uv run pytest tests/test_store_env_config.py -v -k embedder`
Expected: 2 failures.

- [ ] **Step 3: Extend `Store.config()` to read embedder env**

At the end of `Store.config()` (after the `if llm_base_url:` block, before `return cfg`), add:

```python
embedder_provider = os.environ.get("MEM0_EMBEDDER_PROVIDER")
if embedder_provider:
    embedder_config: dict[str, Any] = {}
    if model := os.environ.get("MEM0_EMBEDDER_MODEL"):
        embedder_config["model"] = model
    cfg["embedder"] = {"provider": embedder_provider, "config": embedder_config}
```

- [ ] **Step 4: Verify all env tests pass**

Run: `cd scripts/mem0-memory && uv run pytest tests/test_store_env_config.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/mem0-memory/src/mem0_memory/store.py \
        scripts/mem0-memory/tests/test_store_env_config.py
git commit -m "feat(mem0-memory): Store.config injects embedder block from MEM0_EMBEDDER_* env"
```

---

## Phase 4 — Doctor + docs + release

### Task 9: `doctor` reports active LLM + embedder mode; add `[local-embedder]` extra

**Files:**
- Modify: `scripts/mem0-memory/src/mem0_memory/cli.py` (`doctor_cmd`)
- Modify: `scripts/mem0-memory/tests/test_doctor.py`
- Modify: `scripts/mem0-memory/pyproject.toml`

- [ ] **Step 1: Write the failing doctor test**

Append to `scripts/mem0-memory/tests/test_doctor.py` (the existing file already imports `json`, `cli_mod`, and provides a `runner` fixture — use them):

```python
def test_doctor_reports_proxy_mode(runner, monkeypatch):
    monkeypatch.setenv("MEM0_LLM_BASE_URL", "http://localhost:8765/v1")
    monkeypatch.setenv("MEM0_EMBEDDER_PROVIDER", "fastembed")
    result = runner.invoke(cli_mod.main, ["doctor"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["checks"]["llm_mode"] == "proxy"
    assert payload["checks"]["llm_base_url"] == "http://localhost:8765/v1"
    assert payload["checks"]["embedder_mode"] == "fastembed"


def test_doctor_reports_openai_default_mode(runner, monkeypatch):
    for k in ("MEM0_LLM_BASE_URL", "MEM0_LLM_API_KEY", "MEM0_LLM_MODEL",
              "MEM0_EMBEDDER_PROVIDER", "MEM0_EMBEDDER_MODEL"):
        monkeypatch.delenv(k, raising=False)
    result = runner.invoke(cli_mod.main, ["doctor"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["checks"]["llm_mode"] == "openai-default"
    assert payload["checks"]["embedder_mode"] == "openai-default"
```

- [ ] **Step 2: Run to confirm red**

Run: `cd scripts/mem0-memory && uv run pytest tests/test_doctor.py -v -k "mode"`
Expected: 2 failures (no `llm_mode` field in output).

- [ ] **Step 3: Extend `doctor_cmd` in `cli.py`**

In `scripts/mem0-memory/src/mem0_memory/cli.py`:

1. Ensure `import os` is present at the top of the file (skip if already there).
2. Change the type annotation on the `checks` dict from `dict[str, bool]` to `dict[str, Any]` so it accepts string values. Make sure `Any` is imported from `typing`.
3. Immediately before the final `emit(ok(checks=checks))` line at the end of `doctor_cmd`, insert:

```python
    llm_base_url = os.environ.get("MEM0_LLM_BASE_URL")
    embedder_provider = os.environ.get("MEM0_EMBEDDER_PROVIDER")
    checks["llm_mode"] = "proxy" if llm_base_url else "openai-default"
    checks["llm_base_url"] = llm_base_url
    checks["embedder_mode"] = embedder_provider or "openai-default"
```

The full last 8 lines of `doctor_cmd` should now read:

```python
            checks["sqlite_healthy"] = True

    llm_base_url = os.environ.get("MEM0_LLM_BASE_URL")
    embedder_provider = os.environ.get("MEM0_EMBEDDER_PROVIDER")
    checks["llm_mode"] = "proxy" if llm_base_url else "openai-default"
    checks["llm_base_url"] = llm_base_url
    checks["embedder_mode"] = embedder_provider or "openai-default"

    emit(ok(checks=checks))
```

- [ ] **Step 4: Add `local-embedder` extra to pyproject.toml**

In `scripts/mem0-memory/pyproject.toml`, replace:

```toml
[project.optional-dependencies]
dev = ["pytest>=8"]
```

with:

```toml
[project.optional-dependencies]
dev = ["pytest>=8"]
local-embedder = ["fastembed>=0.8"]
```

- [ ] **Step 5: Run doctor tests**

Run: `cd scripts/mem0-memory && uv run pytest tests/test_doctor.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/mem0-memory/src/mem0_memory/cli.py \
        scripts/mem0-memory/tests/test_doctor.py \
        scripts/mem0-memory/pyproject.toml
git commit -m "feat(mem0-memory): doctor reports LLM/embedder mode + add [local-embedder] extra"
```

---

### Task 10: README "Modes" section + SOUL note

**Files:**
- Modify: `scripts/mem0-memory/README.md`
- Modify: `profiles/seb/SOUL.md`

- [ ] **Step 1: Insert a "Modes" section in `scripts/mem0-memory/README.md`**

Insert this new section immediately after the existing "Installation" section (or near the top if there is no Install heading — read the file first to find the natural slot):

```markdown
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

The output's `data.llm_mode` and `data.embedder_mode` fields say `proxy` or
`openai-default` (or the embedder provider name).
```

- [ ] **Step 2: Append a Memory-routing note to `profiles/seb/SOUL.md`**

Find the "Memory access" section in `profiles/seb/SOUL.md` and append (at the end of that section):

```markdown
> If `MEM0_LLM_BASE_URL=http://localhost:8765/v1` is set in the environment,
> `hpk-memory` automatically routes fact extraction through `codex-openai-proxy`
> — no OpenAI billing key required. See `scripts/mem0-memory/README.md` § Modes.
```

- [ ] **Step 3: Commit**

```bash
git add scripts/mem0-memory/README.md profiles/seb/SOUL.md
git commit -m "docs(mem0-memory): document proxy/OpenAI/hybrid modes + seb SOUL routing note"
```

---

### Task 11: Version bumps + CHANGELOG + final test run

**Files:**
- Modify: `pyproject.toml` (root)
- Modify: `scripts/mem0-memory/pyproject.toml`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Bump versions**

Root `pyproject.toml`: change `version = "3.2.0"` → `version = "3.2.1"`.

`scripts/mem0-memory/pyproject.toml`: change `version = "0.1.0"` → `version = "0.2.0"`.

(The proxy version is already bumped in Task 5.)

- [ ] **Step 2: Add the CHANGELOG entry**

Insert this block in `CHANGELOG.md` immediately below the `## [Unreleased]` heading and above `## [3.2.0]`:

```markdown
## [3.2.1] — 2026-05-16

### Added
- `codex-openai-proxy` 0.2.0: migrated to today's `codex exec --json -` CLI. The old `codex responses --input-json` invocation was broken against `codex-cli >= 0.130`; tests now include a gated `CODEX_PROXY_INTEGRATION=1` contract check so future CLI drift surfaces immediately.
- `mem0-memory` 0.2.0: `Store.config()` honors `MEM0_LLM_BASE_URL` / `MEM0_LLM_API_KEY` / `MEM0_LLM_MODEL` / `MEM0_EMBEDDER_PROVIDER` / `MEM0_EMBEDDER_MODEL` env vars, enabling true "zero external billing keys" mode when paired with `codex-openai-proxy` + a local `fastembed` model.
- `mem0-memory` 0.2.0: new `[local-embedder]` extra (`uv pip install -e ".[local-embedder]"`) brings in `fastembed` for OpenAI-free embeddings.
- `mem0-memory` 0.2.0: `hpk-memory doctor` now reports the active LLM / embedder mode (`proxy`, `openai-default`, or the provider name).
- `scripts/mem0-memory/README.md`: new "Modes" section documenting proxy / OpenAI / hybrid configurations.
- `profiles/seb/SOUL.md`: 1-line routing note covering the proxy mode.

### Fixed
- `mem0-memory` 0.2.0: `Store.add` no longer loses data on silent extraction failure. v3.2.0 relied on mem0 v2 raising on LLM errors, but mem0 v2 actually swallows them and returns `{"results": []}` — so the spec's "any add either becomes a fact OR a raw row" promise was broken when the LLM was misconfigured. Now `Store.add` inspects the result and falls back to `raw_facts` whenever extraction returns empty for non-empty input; the return dict gains `extracted: bool` and `raw_id: int | None` fields.

### Notes
- v3.2.0 users with `OPENAI_API_KEY` set keep working unchanged — the env-driven config blocks are additive and absent envs leave mem0 on its built-in OpenAI defaults.
```

- [ ] **Step 3: Run the entire test surface**

```bash
# Plugin: codex-openai-proxy
cd scripts/codex-openai-proxy && uv run pytest -v
# Plugin: mem0-memory
cd ../mem0-memory && uv run pytest -v
# Root: hpk tests (including e2e)
cd ../.. && uv run pytest -v
```

Expected: all tests pass (skipping the `CODEX_PROXY_INTEGRATION` test by default).

- [ ] **Step 4: Manual end-to-end PoC re-run**

Re-run the original PoC to confirm the previously-broken path now succeeds:

```bash
cd /Users/genie/dev/tools/hermes-profile-kit/scripts/codex-openai-proxy
uv run uvicorn proxy:app --port 8765 &
sleep 2
cd /Users/genie/dev/tools/hermes-profile-kit/scripts/mem0-memory
uv pip install -e ".[local-embedder]"
MEM0_LLM_BASE_URL=http://localhost:8765/v1 \
MEM0_EMBEDDER_PROVIDER=fastembed \
MEM0_EMBEDDER_MODEL=BAAI/bge-small-en-v1.5 \
uv run python /tmp/mem0_codex_poc.py
kill %1
```

Expected: PoC's "[4/4] Pass criteria check" prints PASS with at least one extracted-fact item.

- [ ] **Step 5: Final commit**

```bash
git add pyproject.toml scripts/mem0-memory/pyproject.toml CHANGELOG.md
git commit -m "chore(release): v3.2.1 — zero-tokens mem0 via codex proxy + silent-fail fix"
```

---

## Out of scope (deliberate)

- **Manifest default flip.** v3.2.1 keeps `mem0-memory` and `codex-openai-proxy` both at `default: false`. Auto-enabling either changes upgrade behavior for v3.2.0 users — defer to v3.3.
- **Embedder swap for `honcho-memory`.** `honcho-memory` is the upstream-verified default for `assistant` and `research`. It stays untouched.
- **Tagging + push.** The current pattern (see v3.2.0) is for the user to drive the final `git tag` and `git push --tags`. The plan stops at the release commit.
- **Documentation translation.** `README.ko.md` is not updated as part of this plan; the English README/CHANGELOG is the source of truth.
