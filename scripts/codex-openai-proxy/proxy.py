"""Local OpenAI-compatible proxy routing /v1/chat/completions to `codex responses` CLI.

Translation layer:
  OpenAI Chat Completions (input) → OpenAI Responses API format → codex CLI stdin
  codex CLI stdout (Responses API format) → OpenAI Chat Completions (output)

If the codex CLI interface changes, update _to_responses_payload() and
_extract_content() only — the HTTP layer and test surface stay unchanged.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

PORT = int(os.environ.get("CODEX_PROXY_PORT", "8765"))
MODELS = os.environ.get("CODEX_PROXY_MODELS", "gpt-5.5,gpt-5.4-mini").split(",")

app = FastAPI(title="codex-openai-proxy", version="0.1.0")


# ── Translation helpers ────────────────────────────────────────────────────────

def _to_responses_payload(body: dict) -> dict:
    """Convert Chat Completions request body to Responses API payload for codex CLI."""
    messages: list[dict] = body.get("messages", [])
    instructions: str | None = None
    turns: list[dict] = []

    for msg in messages:
        role = msg["role"]
        content = msg.get("content") or ""
        if isinstance(content, list):
            # Multi-part content — extract text parts only.
            content = " ".join(
                part.get("text", "") for part in content if part.get("type") == "text"
            )
        if role == "system":
            instructions = content
        elif role == "user":
            turns.append({
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": content}],
            })
        elif role == "assistant":
            turns.append({
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": content}],
            })

    # Single user message: use simpler string form accepted by Responses API.
    if len(turns) == 1 and turns[0]["role"] == "user":
        user_text = turns[0]["content"][0]["text"]
        payload: dict = {"model": body.get("model", MODELS[0]), "input": user_text}
    else:
        payload = {"model": body.get("model", MODELS[0]), "input": turns}

    if instructions:
        payload["instructions"] = instructions
    if tools := body.get("tools"):
        payload["tools"] = tools

    return payload


def _extract_content(response_bytes: bytes) -> str:
    """Extract assistant text from Responses API JSON output."""
    try:
        data = json.loads(response_bytes)
    except json.JSONDecodeError:
        return response_bytes.decode(errors="replace")

    for item in data.get("output", []):
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    return str(part["text"])
    # Fallback: return raw output (e.g. if codex returns plain text).
    return response_bytes.decode(errors="replace").strip()


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
    payload = _to_responses_payload(body)
    stdin_data = json.dumps(payload).encode()

    try:
        proc = subprocess.Popen(
            ["codex", "responses", "--model", model, "--input-json", "-"],
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
            _stream(proc, stdin_data, model),
            media_type="text/event-stream",
        )

    # Non-streaming: wait for full response.
    stdout, stderr = proc.communicate(stdin_data)
    if proc.returncode != 0:
        if _is_auth_error(stderr):
            raise HTTPException(
                502,
                detail={
                    "error": {
                        "message": "Run `codex auth login` first",
                        "type": "codex_auth_required",
                    }
                },
            )
        raise HTTPException(
            502,
            detail={
                "error": {
                    "message": stderr.decode(errors="replace").strip(),
                    "type": "codex_error",
                }
            },
        )

    content = _extract_content(stdout)
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
    """Yield OpenAI SSE chunks wrapping the full Codex response."""
    loop = asyncio.get_running_loop()
    stdout, stderr = await loop.run_in_executor(None, proc.communicate, stdin_data)

    if proc.returncode != 0:
        error_text = (
            "Run `codex auth login` first" if _is_auth_error(stderr)
            else stderr.decode(errors="replace").strip()
        )
        yield f"data: {json.dumps({'error': {'message': error_text, 'type': 'codex_error'}})}\n\n"
        yield "data: [DONE]\n\n"
        return

    content = _extract_content(stdout)

    # Content chunk.
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

    # Stop chunk.
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
