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

def _fake_popen(agent_text: str = "Hello world", returncode: int = 0, stderr: bytes = b""):
    """Mock Popen returning codex-exec-style JSONL stdout, suitable for both
    proc.communicate() AND the streaming readline-based reader."""
    mock = MagicMock()
    jsonl_lines = [
        b'{"type":"thread.started","thread_id":"x"}\n',
        b'{"type":"turn.started"}\n',
        json.dumps({
            "type": "item.completed",
            "item": {"id": "i0", "type": "agent_message", "text": agent_text},
        }).encode() + b"\n",
        b'{"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":2}}\n',
    ]
    # iter(readline, b'') iterates until b'' is returned, so terminate with b''
    mock.stdout.readline.side_effect = jsonl_lines + [b""]
    mock.stderr.read.return_value = stderr
    mock.stdin = MagicMock()
    mock.returncode = returncode
    mock.poll.return_value = returncode  # already finished
    mock.communicate.return_value = (b"".join(jsonl_lines), stderr)  # legacy support
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


def test_system_message_renders_into_stdin_prompt(client):
    """System messages are rendered as [system]\\n{text} blocks in the codex exec stdin."""
    captured: dict = {}

    def capturing_popen(cmd, **kwargs):
        mock = _fake_popen("ok")
        original_write = mock.stdin.write
        def capturing_write(data):
            captured["stdin"] = data.decode()
            return original_write(data)
        mock.stdin.write = capturing_write
        return mock

    with patch("subprocess.Popen", side_effect=capturing_popen):
        client.post("/v1/chat/completions", json={
            "model": "gpt-5.5",
            "messages": [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Hi"},
            ],
        })
    assert captured["stdin"] == "[system]\nYou are helpful\n\n[user]\nHi"


def _fake_popen_error(stderr: bytes, returncode: int = 1):
    """Mock Popen that returns no useful stdout and a non-zero returncode."""
    mock = MagicMock()
    mock.stdout.readline.side_effect = [b""]  # EOF immediately — no events
    mock.stderr.read.return_value = stderr
    mock.stdin = MagicMock()
    mock.returncode = returncode
    mock.poll.return_value = returncode
    return mock


def test_codex_auth_error_returns_502_with_hint(client):
    mock = _fake_popen_error(b"error: not authenticated, run codex auth login")
    with patch("subprocess.Popen", return_value=mock):
        r = client.post("/v1/chat/completions", json={
            "model": "gpt-5.5",
            "messages": [{"role": "user", "content": "hi"}],
        })
    assert r.status_code == 502
    assert "codex login" in r.json()["detail"]["error"]["message"]


def test_codex_non_auth_error_returns_502_with_stderr(client):
    """Non-zero returncode without auth markers → 502 codex_error with stderr surfaced."""
    mock = _fake_popen_error(b"error: rate limited")
    with patch("subprocess.Popen", return_value=mock):
        r = client.post("/v1/chat/completions", json={
            "model": "gpt-5.5",
            "messages": [{"role": "user", "content": "hi"}],
        })
    assert r.status_code == 502
    assert r.json()["detail"]["error"]["type"] == "codex_error"
    assert "rate limited" in r.json()["detail"]["error"]["message"]


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


# ── Early termination ─────────────────────────────────────────────────────────

def test_run_codex_terminates_after_turn_completed():
    """After turn.completed is read from stdout, the process is terminated."""
    from proxy import _run_codex_until_done
    mock_proc = _fake_popen("hello")
    # Simulate process still running after turn.completed seen
    mock_proc.poll.return_value = None  # alive
    mock_proc.wait.return_value = 0

    with patch("subprocess.Popen", return_value=mock_proc):
        stdout, stderr, rc = _run_codex_until_done(["--json", "-"], b"prompt")

    # The reader should have stopped after turn.completed, then terminate() called
    mock_proc.terminate.assert_called_once()
    # Stdout should contain the 4 JSONL lines we mocked
    assert b'agent_message' in stdout
    assert b'turn.completed' in stdout


def test_run_codex_hard_timeout_kills_process():
    """If turn.completed never arrives, hard timeout kills the process."""
    import threading as _threading
    from proxy import _run_codex_until_done

    mock_proc = MagicMock()
    # Use an event to make readline block until kill() unblocks it.
    unblock = _threading.Event()

    def blocking_readline():
        # First call: return a non-terminal line (no turn.completed).
        # Subsequent calls: block until unblocked, then return EOF.
        if not getattr(blocking_readline, "_first", False):
            blocking_readline._first = True
            return b'{"type":"thread.started"}\n'
        unblock.wait(timeout=5)
        return b""

    mock_proc.stdout.readline.side_effect = blocking_readline
    mock_proc.stderr.read.return_value = b""
    mock_proc.stdin = MagicMock()
    mock_proc.poll.return_value = None
    mock_proc.returncode = -9  # SIGKILL

    # When kill() is called, unblock the blocking readline so the reader exits.
    mock_proc.kill.side_effect = lambda: unblock.set()

    with patch("subprocess.Popen", return_value=mock_proc):
        stdout, stderr, rc = _run_codex_until_done(["--json", "-"], b"prompt", timeout=0.2)

    # Hard timeout should have called kill()
    mock_proc.kill.assert_called_once()
    assert rc == -9
