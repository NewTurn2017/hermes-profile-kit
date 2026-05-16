"""Unit tests for hpk.env_file — parse + key-level merge with .env.bak snapshot."""

from __future__ import annotations

from pathlib import Path

import pytest

from hpk.env_file import EnvFileParseError, load_env_file, merge_into_env


def test_load_env_file_parses_keys_and_skips_comments_blanks(tmp_path: Path) -> None:
    src = tmp_path / "tokens.env"
    src.write_text(
        "# comment\n"
        "\n"
        "SLACK_BOT_TOKEN=xoxb-abc\n"
        "  # leading spaces on comment\n"
        "SLACK_APP_TOKEN=xapp-xyz\n"
    )
    assert load_env_file(src) == {
        "SLACK_BOT_TOKEN": "xoxb-abc",
        "SLACK_APP_TOKEN": "xapp-xyz",
    }


def test_load_env_file_rejects_malformed_line(tmp_path: Path) -> None:
    src = tmp_path / "bad.env"
    src.write_text("not a key=val pair line\nSLACK_BOT_TOKEN=xoxb\n")
    with pytest.raises(EnvFileParseError, match="line 1"):
        load_env_file(src)


def test_load_env_file_rejects_lowercase_key(tmp_path: Path) -> None:
    src = tmp_path / "bad.env"
    src.write_text("slack_bot=xoxb\n")
    with pytest.raises(EnvFileParseError):
        load_env_file(src)


def test_merge_into_env_updates_only_named_keys_and_preserves_siblings(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("SLACK_BOT_TOKEN=old\nUNRELATED_KEY=keep_me\nSLACK_APP_TOKEN=FILL_IN\n")
    merge_into_env(env, {"SLACK_BOT_TOKEN": "xoxb-new", "SLACK_APP_TOKEN": "xapp-new"})
    text = env.read_text()
    assert "SLACK_BOT_TOKEN=xoxb-new" in text
    assert "SLACK_APP_TOKEN=xapp-new" in text
    assert "UNRELATED_KEY=keep_me" in text
    assert "old" not in text


def test_merge_into_env_writes_dot_env_bak_with_prior_contents(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("SLACK_BOT_TOKEN=old\n")
    merge_into_env(env, {"SLACK_BOT_TOKEN": "xoxb-new"})
    bak = tmp_path / ".env.bak"
    assert bak.exists()
    assert bak.read_text() == "SLACK_BOT_TOKEN=old\n"


def test_merge_into_env_overwrites_existing_dot_env_bak_on_rerun(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("SLACK_BOT_TOKEN=v1\n")
    merge_into_env(env, {"SLACK_BOT_TOKEN": "v2"})
    merge_into_env(env, {"SLACK_BOT_TOKEN": "v3"})
    assert (tmp_path / ".env.bak").read_text() == "SLACK_BOT_TOKEN=v2\n"
    assert (tmp_path / ".env").read_text().strip() == "SLACK_BOT_TOKEN=v3"


def test_merge_into_env_creates_missing_env_with_0600(tmp_path: Path) -> None:
    env = tmp_path / "subdir" / ".env"
    merge_into_env(env, {"SLACK_BOT_TOKEN": "xoxb-new"})
    assert env.read_text() == "SLACK_BOT_TOKEN=xoxb-new\n"
    assert oct(env.stat().st_mode & 0o777) == "0o600"
    # No backup for an absent prior file.
    assert not (tmp_path / "subdir" / ".env.bak").exists()


def test_merge_into_env_appends_new_keys_when_absent(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("EXISTING=1\n")
    merge_into_env(env, {"NEW_KEY": "v"})
    text = env.read_text()
    assert "EXISTING=1" in text
    assert "NEW_KEY=v" in text
