"""phase_b_tokens / phase_c_plugins under non-interactive mode + overrides."""

from __future__ import annotations

import pytest

from hpk import wizard
from hpk.manifest import Plugin, Profile, RecommendedPlugin, TokenSpec, TokensSection
from hpk.wizard import (
    NonInteractiveMissingError,
    UnknownPluginIdError,
    UnknownTokenKeyError,
    phase_b_tokens,
    phase_c_plugins,
)


def _seb_profile() -> Profile:
    return Profile(
        name="seb",
        template="profiles/seb",
        role="second brain",
        model_tier="openai-codex",
        channels=["slack"],
        tokens=TokensSection(
            required=[
                TokenSpec(key="SLACK_BOT_TOKEN", provider="slack", wizard="slack_bot"),
                TokenSpec(key="SLACK_SIGNING_SECRET", provider="slack", wizard="slack_signing"),
                TokenSpec(key="SLACK_APP_TOKEN", provider="slack", wizard="slack_app"),
                TokenSpec(
                    key="OPENAI_BASE_URL",
                    provider="openai-codex",
                    wizard="codex_base_url",
                    default="http://localhost:8765/v1",
                ),
            ],
            optional=[],
        ),
        recommended_plugins=[RecommendedPlugin(id="codex-openai-proxy", default=True)],
    )


_BOT = "xoxb-" + "0" * 30
_SIGN = "a" * 32
_APP = "xapp-" + "0" * 30


def test_phase_b_with_all_tokens_via_flags_writes_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = _seb_profile()
    phase_b_tokens(
        p,
        non_interactive=True,
        token_overrides={
            "SLACK_BOT_TOKEN": _BOT,
            "SLACK_SIGNING_SECRET": _SIGN,
            "SLACK_APP_TOKEN": _APP,
        },
        env_file_values={},
    )
    env = (tmp_path / ".hermes" / "profiles" / "seb" / ".env").read_text()
    assert f"SLACK_BOT_TOKEN={_BOT}" in env
    assert f"SLACK_SIGNING_SECRET={_SIGN}" in env
    assert f"SLACK_APP_TOKEN={_APP}" in env
    # Default-bearing token uses its manifest default under non-interactive.
    assert "OPENAI_BASE_URL=http://localhost:8765/v1" in env


def test_phase_b_snapshots_existing_env_to_bak_when_flags_used(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    home = tmp_path / ".hermes" / "profiles" / "seb"
    home.mkdir(parents=True)
    (home / ".env").write_text("SLACK_BOT_TOKEN=old-value\nUNRELATED=keep\n")
    p = _seb_profile()
    phase_b_tokens(
        p,
        non_interactive=True,
        token_overrides={
            "SLACK_BOT_TOKEN": _BOT,
            "SLACK_SIGNING_SECRET": _SIGN,
            "SLACK_APP_TOKEN": _APP,
        },
        env_file_values={},
    )
    bak = (home / ".env.bak").read_text()
    assert "SLACK_BOT_TOKEN=old-value" in bak
    assert "UNRELATED=keep" in bak
    env = (home / ".env").read_text()
    assert f"SLACK_BOT_TOKEN={_BOT}" in env
    assert "UNRELATED=keep" in env
    assert "old-value" not in env


def test_phase_b_non_interactive_missing_required_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = _seb_profile()
    with pytest.raises(NonInteractiveMissingError) as exc:
        phase_b_tokens(
            p,
            non_interactive=True,
            token_overrides={"SLACK_BOT_TOKEN": _BOT},  # 2 required still missing
            env_file_values={},
        )
    msg = str(exc.value)
    assert "SLACK_SIGNING_SECRET" in msg
    assert "SLACK_APP_TOKEN" in msg


def test_phase_b_token_flag_beats_env_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = _seb_profile()
    phase_b_tokens(
        p,
        non_interactive=True,
        token_overrides={"SLACK_BOT_TOKEN": _BOT},
        env_file_values={
            "SLACK_BOT_TOKEN": "xoxb-fromfile",
            "SLACK_SIGNING_SECRET": _SIGN,
            "SLACK_APP_TOKEN": _APP,
        },
    )
    env = (tmp_path / ".hermes" / "profiles" / "seb" / ".env").read_text()
    assert f"SLACK_BOT_TOKEN={_BOT}" in env
    assert "xoxb-fromfile" not in env


def test_phase_b_validation_failure_via_flag_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = _seb_profile()
    with pytest.raises(NonInteractiveMissingError, match="SLACK_BOT_TOKEN"):
        phase_b_tokens(
            p,
            non_interactive=True,
            token_overrides={
                "SLACK_BOT_TOKEN": "not-xoxb-prefixed",
                "SLACK_SIGNING_SECRET": _SIGN,
                "SLACK_APP_TOKEN": _APP,
            },
            env_file_values={},
        )


def test_phase_b_unknown_token_key_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = _seb_profile()
    with pytest.raises(UnknownTokenKeyError, match="NOT_A_KEY"):
        phase_b_tokens(
            p,
            non_interactive=True,
            token_overrides={"NOT_A_KEY": "x"},
            env_file_values={},
        )


def _make_catalog() -> dict[str, Plugin]:
    return {
        "codex-openai-proxy": Plugin(
            description="local proxy",
            upstream_command=None,
            install_path="scripts/codex-openai-proxy",
            launchd_template=None,
            verified_in_upstream=False,
            docs=None,
        ),
    }


def test_phase_c_accept_flag_overrides_default_false(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = _seb_profile()
    p.recommended_plugins = [RecommendedPlugin(id="codex-openai-proxy", default=False)]
    asked: list[str] = []
    monkeypatch.setattr(wizard, "_ask_plugin", lambda pid, default: asked.append(pid) or True)
    phase_c_plugins(
        p,
        _make_catalog(),
        non_interactive=True,
        accepted_plugins={"codex-openai-proxy"},
        rejected_plugins=set(),
    )
    assert asked == []  # never prompted in non-interactive


def test_phase_c_reject_beats_accept_on_same_id(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = _seb_profile()
    warnings: list[str] = []
    monkeypatch.setattr(wizard.ui, "warn", lambda msg: warnings.append(msg))
    phase_c_plugins(
        p,
        _make_catalog(),
        non_interactive=True,
        accepted_plugins={"codex-openai-proxy"},
        rejected_plugins={"codex-openai-proxy"},
    )
    assert any("codex-openai-proxy" in w and "reject" in w.lower() for w in warnings)


def test_phase_c_unknown_plugin_id_in_flags_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = _seb_profile()
    with pytest.raises(UnknownPluginIdError, match="not-a-plugin"):
        phase_c_plugins(
            p,
            _make_catalog(),
            non_interactive=True,
            accepted_plugins={"not-a-plugin"},
            rejected_plugins=set(),
        )
