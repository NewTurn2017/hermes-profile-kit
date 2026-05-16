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
