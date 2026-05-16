"""doctor: import check + dir check + sqlite check."""
from __future__ import annotations

import json
import pytest
from click.testing import CliRunner

from mem0_memory import cli as cli_mod
from mem0_memory.paths import profile_memory_dir


@pytest.fixture
def runner(hermes_home, fake_memory_factory, monkeypatch):
    monkeypatch.setattr(cli_mod, "_memory_factory", fake_memory_factory)
    return CliRunner()


def test_doctor_green(runner, hermes_home):
    # Create the seb profile memory dir by issuing one add
    runner.invoke(cli_mod.main, ["add", "--profile", "seb", "--text", "warmup"])
    result = runner.invoke(cli_mod.main, ["doctor", "--profile", "seb"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["checks"]["mem0_import"] is True
    assert payload["checks"]["profile_dir"] is True
    assert payload["checks"]["sqlite_healthy"] is True


def test_doctor_red_when_mem0_import_fails(runner, monkeypatch):
    _real_import = __import__

    def boom(name: str, *a, **kw):
        if name == "mem0":
            raise ImportError("mem0 not installed")
        return _real_import(name, *a, **kw)
    monkeypatch.setattr("builtins.__import__", boom)
    result = runner.invoke(cli_mod.main, ["doctor", "--profile", "seb"])
    assert result.exit_code == 20
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["kind"] == "mem0_import_failed"


def test_doctor_red_when_sqlite_corrupt(runner, hermes_home):
    runner.invoke(cli_mod.main, ["add", "--profile", "seb", "--text", "warmup"])
    sqlite_path = profile_memory_dir("seb") / "store.sqlite"
    sqlite_path.write_bytes(b"NOT A SQLITE FILE")
    result = runner.invoke(cli_mod.main, ["doctor", "--profile", "seb"])
    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["kind"] == "sqlite_unhealthy"


def test_doctor_no_profile_omits_profile_checks(runner):
    result = runner.invoke(cli_mod.main, ["doctor"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["checks"]["mem0_import"] is True
    # profile-specific keys must NOT be present when --profile is omitted
    assert "profile_dir" not in payload["checks"]
    assert "sqlite_healthy" not in payload["checks"]


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
