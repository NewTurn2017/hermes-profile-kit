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
