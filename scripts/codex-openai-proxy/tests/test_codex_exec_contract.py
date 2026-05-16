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
