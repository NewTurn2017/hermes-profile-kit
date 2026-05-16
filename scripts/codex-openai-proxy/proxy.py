"""Local OpenAI-compatible proxy routing /v1/chat/completions to `codex exec --json -`.

Translation layer:
  OpenAI Chat Completions (input) → rendered [role] prompt → codex exec stdin
  codex exec stdout (JSONL events) → parsed agent_message text → OpenAI Chat Completions (output)

If the codex CLI interface changes, update _to_codex_exec_invocation() and
_parse_codex_jsonl_events() — the HTTP layer and test surface stay unchanged.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

PORT = int(os.environ.get("CODEX_PROXY_PORT", "8765"))
MODELS = os.environ.get("CODEX_PROXY_MODELS", "gpt-5.5,gpt-5.4-mini").split(",")

app = FastAPI(title="codex-openai-proxy", version="0.1.0")


# ── Translation helpers ────────────────────────────────────────────────────────

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
    """Parse `codex exec --json` output. Returns (assistant_text, error_or_None).

    Both fields may be populated if the stream contains agent_message events
    AND an error/turn.failed event; callers should treat a non-None error as
    authoritative (HTTP 502) even when text is also present.
    """
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


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/v1/models")
async def list_models() -> dict:
    return {
        "object": "list",
        "data": [{"id": m, "object": "model", "owned_by": "codex-proxy"} for m in MODELS],
    }


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


def main() -> None:
    uvicorn.run(app, host="127.0.0.1", port=PORT)


if __name__ == "__main__":
    main()
