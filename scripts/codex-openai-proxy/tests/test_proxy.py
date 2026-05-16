"""Tests for codex-openai-proxy. Uses TestClient to avoid spinning up a real server.
Codex CLI calls are mocked — no real 'codex' binary required."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from proxy import app
    return TestClient(app)


# ── /v1/models ────────────────────────────────────────────────────────────────

def test_list_models_returns_configured_models(client):
    r = client.get("/v1/models")
    assert r.status_code == 200
    ids = [m["id"] for m in r.json()["data"]]
    assert "gpt-5.5" in ids
    assert "gpt-5.4-mini" in ids


# ── /v1/chat/completions (non-streaming) ──────────────────────────────────────

def _fake_popen(stdout_text: str, returncode: int = 0):
    """Return a mock Popen that produces a fixed stdout."""
    mock = MagicMock()
    mock.communicate.return_value = (
        json.dumps({
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": stdout_text}],
                }
            ]
        }).encode(),
        b"",
    )
    mock.returncode = returncode
    return mock


def test_chat_completions_non_streaming_returns_content(client):
    with patch("subprocess.Popen", return_value=_fake_popen("Hello world")):
        r = client.post("/v1/chat/completions", json={
            "model": "gpt-5.5",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": False,
        })
    assert r.status_code == 200
    data = r.json()
    assert data["choices"][0]["message"]["content"] == "Hello world"
    assert data["choices"][0]["finish_reason"] == "stop"
    assert data["object"] == "chat.completion"


def test_chat_completions_passes_model_to_codex(client):
    with patch("subprocess.Popen", return_value=_fake_popen("ok")) as mock_popen:
        client.post("/v1/chat/completions", json={
            "model": "gpt-5.4-mini",
            "messages": [{"role": "user", "content": "ping"}],
        })
    call_args = mock_popen.call_args[0][0]
    assert "gpt-5.4-mini" in call_args


def test_system_message_becomes_instructions(client):
    captured = {}
    def fake_popen(cmd, stdin, stdout, stderr):
        # Read stdin to check what was sent to codex
        mock = _fake_popen("ok")
        original_communicate = mock.communicate
        def capturing_communicate(input_data=None):
            if input_data:
                captured["payload"] = json.loads(input_data.decode())
            return original_communicate(input_data)
        mock.communicate = capturing_communicate
        return mock

    with patch("subprocess.Popen", side_effect=fake_popen):
        client.post("/v1/chat/completions", json={
            "model": "gpt-5.5",
            "messages": [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Hi"},
            ],
        })
    assert captured.get("payload", {}).get("instructions") == "You are helpful"


def test_codex_auth_error_returns_502_with_hint(client):
    mock = MagicMock()
    mock.communicate.return_value = (b"", b"error: not authenticated, run codex auth login")
    mock.returncode = 1
    with patch("subprocess.Popen", return_value=mock):
        r = client.post("/v1/chat/completions", json={
            "model": "gpt-5.5",
            "messages": [{"role": "user", "content": "hi"}],
        })
    assert r.status_code == 502
    assert "codex auth login" in r.json()["detail"]["error"]["message"]


def test_codex_not_found_returns_502(client):
    with patch("subprocess.Popen", side_effect=FileNotFoundError("codex not found")):
        r = client.post("/v1/chat/completions", json={
            "model": "gpt-5.5",
            "messages": [{"role": "user", "content": "hi"}],
        })
    assert r.status_code == 502
    assert "codex" in r.json()["detail"]["error"]["message"].lower()


# ── /v1/chat/completions (streaming) ─────────────────────────────────────────

def test_chat_completions_streaming_returns_sse(client):
    with patch("subprocess.Popen", return_value=_fake_popen("streamed content")):
        with client.stream("POST", "/v1/chat/completions", json={
            "model": "gpt-5.5",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        }) as r:
            assert r.status_code == 200
            raw = r.read().decode()
    chunks = raw.strip().split("\n\n")
    data_lines = [c for c in chunks if c.startswith("data: ") and "[DONE]" not in c]
    assert len(data_lines) >= 1
    first = json.loads(data_lines[0][6:])
    assert first["object"] == "chat.completion.chunk"
    assert "streamed content" in first["choices"][0]["delta"]["content"]


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
