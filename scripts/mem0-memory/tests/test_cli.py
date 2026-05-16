"""CLI: argument parsing, exit codes, JSON envelope, write-path guards."""
from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from mem0_memory import cli as cli_mod


@pytest.fixture
def runner(hermes_home, fake_memory_factory, monkeypatch):
    monkeypatch.setattr(cli_mod, "_memory_factory", fake_memory_factory)
    return CliRunner()


def _invoke(runner: CliRunner, args: list[str]):
    result = runner.invoke(cli_mod.main, args)
    payload = json.loads(result.output) if result.output.strip() else {}
    return result, payload


def test_add_returns_ok_envelope(runner):
    result, payload = _invoke(runner, ["add", "--profile", "seb", "--text", "hello"])
    assert result.exit_code == 0
    assert payload["ok"] is True
    assert payload["scope"] == "profile"
    assert "id" in payload


def test_add_rejects_scope_flag(runner):
    result, payload = _invoke(
        runner, ["add", "--profile", "seb", "--text", "hello", "--scope", "shared"]
    )
    assert result.exit_code == 1
    assert payload["ok"] is False
    assert payload["kind"] == "shared_write_forbidden"


def test_add_requires_profile(runner):
    result = runner.invoke(cli_mod.main, ["add", "--text", "x"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["kind"] == "missing_arg"


def test_add_requires_text(runner):
    result = runner.invoke(cli_mod.main, ["add", "--profile", "seb"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["kind"] == "missing_arg"


def test_share_add_returns_ok_with_shared_scope(runner):
    result, payload = _invoke(runner, ["share-add", "--text", "global fact"])
    assert result.exit_code == 0
    assert payload["ok"] is True
    assert payload["scope"] == "shared"


def test_add_meta_parsed_into_dict(runner):
    result, payload = _invoke(
        runner,
        ["add", "--profile", "seb", "--text", "hi", "--meta", "k=v", "--meta", "a=b"],
    )
    assert result.exit_code == 0
    assert payload["meta"] == {"k": "v", "a": "b"}


def test_add_meta_rejects_malformed(runner):
    result = runner.invoke(
        cli_mod.main, ["add", "--profile", "seb", "--text", "x", "--meta", "no_equals"]
    )
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["kind"] == "bad_meta"


def test_add_rejects_whitespace_only_text(runner):
    result = runner.invoke(
        cli_mod.main, ["add", "--profile", "seb", "--text", "   "]
    )
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["kind"] == "missing_arg"


def test_share_add_rejects_whitespace_only_text(runner):
    result = runner.invoke(cli_mod.main, ["share-add", "--text", "\t \n"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["kind"] == "missing_arg"


# ----- read-path tests -----

def test_query_scope_profile_only(runner):
    runner.invoke(cli_mod.main, ["share-add", "--text", "shared fact"])
    runner.invoke(cli_mod.main, ["add", "--profile", "seb", "--text", "seb fact"])
    result, payload = _invoke(
        runner, ["query", "--profile", "seb", "--q", "fact", "--scope", "profile"]
    )
    assert result.exit_code == 0
    texts = [m["text"] for m in payload["memories"]]
    assert "seb fact" in texts
    assert "shared fact" not in texts


def test_query_scope_shared_only(runner):
    runner.invoke(cli_mod.main, ["share-add", "--text", "shared fact"])
    runner.invoke(cli_mod.main, ["add", "--profile", "seb", "--text", "seb fact"])
    result, payload = _invoke(
        runner, ["query", "--profile", "seb", "--q", "fact", "--scope", "shared"]
    )
    assert result.exit_code == 0
    texts = [m["text"] for m in payload["memories"]]
    assert "shared fact" in texts
    assert "seb fact" not in texts


def test_query_scope_all_merges_profile_and_shared(runner):
    runner.invoke(cli_mod.main, ["share-add", "--text", "shared fact"])
    runner.invoke(cli_mod.main, ["add", "--profile", "seb", "--text", "seb fact"])
    runner.invoke(cli_mod.main, ["add", "--profile", "assistant", "--text", "assistant fact"])
    result, payload = _invoke(
        runner, ["query", "--profile", "seb", "--q", "fact", "--scope", "all"]
    )
    assert result.exit_code == 0
    texts = [m["text"] for m in payload["memories"]]
    assert "seb fact" in texts
    assert "shared fact" in texts
    assert "assistant fact" not in texts
    scopes = {m["scope"] for m in payload["memories"]}
    assert scopes == {"profile", "shared"}


def test_query_scope_default_is_all(runner):
    runner.invoke(cli_mod.main, ["share-add", "--text", "shared fact"])
    runner.invoke(cli_mod.main, ["add", "--profile", "seb", "--text", "seb fact"])
    result, payload = _invoke(runner, ["query", "--profile", "seb", "--q", "fact"])
    texts = {m["text"] for m in payload["memories"]}
    assert texts == {"seb fact", "shared fact"}


def test_query_rejects_unknown_scope(runner):
    result = runner.invoke(
        cli_mod.main, ["query", "--profile", "seb", "--q", "x", "--scope", "bogus"]
    )
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["kind"] == "bad_scope"


def test_query_respects_limit(runner):
    for i in range(5):
        runner.invoke(cli_mod.main, ["add", "--profile", "seb", "--text", f"fact {i}"])
    result, payload = _invoke(
        runner, ["query", "--profile", "seb", "--q", "fact", "--scope", "profile", "--limit", "2"]
    )
    assert len(payload["memories"]) == 2


def test_list_profile(runner):
    runner.invoke(cli_mod.main, ["add", "--profile", "seb", "--text", "x1"])
    runner.invoke(cli_mod.main, ["add", "--profile", "seb", "--text", "x2"])
    result, payload = _invoke(runner, ["list", "--profile", "seb", "--scope", "profile"])
    assert result.exit_code == 0
    assert len(payload["memories"]) == 2


def test_share_list(runner):
    runner.invoke(cli_mod.main, ["share-add", "--text", "g1"])
    runner.invoke(cli_mod.main, ["share-add", "--text", "g2"])
    result, payload = _invoke(runner, ["share-list"])
    assert result.exit_code == 0
    texts = [m["text"] for m in payload["memories"]]
    assert {"g1", "g2"} <= set(texts)
