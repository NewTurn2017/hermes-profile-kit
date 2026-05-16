# ruff: noqa: E501  # YAML fixture preserves manifest layout for readability.
"""E2E: hpk setup seb --non-interactive completes without any interactive read."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from hpk.cli import main as cli_main

_MANIFEST_YAML = """\
schema_version: 3
kit: {name: hpk, version: 3.0.0, license: MIT}
upstream: {repo: x, pinned_commit: abc, pinned_version: 0.12.3, verified_at: 2026-05-15T09:49Z}
min_hermes_version: 0.12.0
profiles:
  - name: seb
    template: profiles/seb
    role: second brain
    model_tier: openai-codex
    channels: [slack]
    tokens:
      required:
        - { key: SLACK_BOT_TOKEN,      provider: slack,        wizard: slack_bot     }
        - { key: SLACK_SIGNING_SECRET, provider: slack,        wizard: slack_signing }
        - { key: SLACK_APP_TOKEN,      provider: slack,        wizard: slack_app     }
        - { key: OPENAI_BASE_URL,      provider: openai-codex, wizard: codex_base_url, default: "http://localhost:8765/v1" }
        - { key: OPENAI_API_KEY,       provider: openai-codex, wizard: codex_api_key,  default: "sk-codex-proxy-local" }
      optional: []
    recommended_plugins:
      - { id: codex-openai-proxy, default: true }
plugins:
  codex-openai-proxy:
    description: local proxy
    upstream_command: null
    install_path: scripts/codex-openai-proxy
    launchd_template: scripts/codex-openai-proxy/launchd.plist.example
    verified_in_upstream: false
    docs: scripts/codex-openai-proxy/README.md
preserve_existing: [.env]
overwrite_from_template: [SOUL.md, config.yaml]
"""

_BOT = "xoxb-" + "0" * 30
_SIGN = "a" * 32
_APP = "xapp-" + "0" * 30


def _scaffold(tmp_path: Path) -> None:
    (tmp_path / "manifest.yaml").write_text(_MANIFEST_YAML)
    tpl = tmp_path / "profiles" / "seb"
    tpl.mkdir(parents=True)
    (tpl / "SOUL.md").write_text("soul")
    (tpl / "config.yaml").write_text("model:\n  default: openai/gpt-5.5\n")
    (tpl / ".env.example").write_text(
        "SLACK_BOT_TOKEN=FILL_IN\n"
        "SLACK_SIGNING_SECRET=FILL_IN\n"
        "SLACK_APP_TOKEN=FILL_IN\n"
        "OPENAI_BASE_URL=http://localhost:8765/v1\n"
        "OPENAI_API_KEY=sk-codex-proxy-local\n"
    )
    (tmp_path / "scripts" / "codex-openai-proxy").mkdir(parents=True)


def test_e2e_seb_non_interactive_completes_with_zero_interactive_reads(
    fake_hermes, tmp_path, monkeypatch
):
    _scaffold(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("hpk.wizard._has_local_bin_on_path", lambda: True)

    # Boobytrap every interactive entry point — touching any of these is the failure mode
    # this test is meant to catch.
    def _explode(*a, **kw):
        raise AssertionError("interactive prompt called during --non-interactive run")

    from hpk import wizard

    monkeypatch.setattr(wizard, "_prompt_secret", _explode)
    monkeypatch.setattr(wizard, "_ask_plugin", _explode)
    monkeypatch.setattr("questionary.password", _explode)
    monkeypatch.setattr("questionary.confirm", _explode)

    r = CliRunner().invoke(
        cli_main,
        [
            "setup",
            "seb",
            "--non-interactive",
            "--token",
            f"SLACK_BOT_TOKEN={_BOT}",
            "--token",
            f"SLACK_SIGNING_SECRET={_SIGN}",
            "--token",
            f"SLACK_APP_TOKEN={_APP}",
            "--accept-plugin",
            "codex-openai-proxy",
        ],
    )
    assert r.exit_code == 0, r.output

    env = (tmp_path / ".hermes" / "profiles" / "seb" / ".env").read_text()
    assert f"SLACK_BOT_TOKEN={_BOT}" in env
    assert f"SLACK_SIGNING_SECRET={_SIGN}" in env
    assert f"SLACK_APP_TOKEN={_APP}" in env
    assert "OPENAI_BASE_URL=http://localhost:8765/v1" in env
    assert "OPENAI_API_KEY=sk-codex-proxy-local" in env

    # hermes was called to create the profile, NOT to install the kit-local proxy.
    assert ["hermes", "profile", "create", "seb"] in fake_hermes.calls
    assert "codex-openai-proxy" not in str(fake_hermes.calls)


def test_e2e_seb_non_interactive_env_file_alone_suffices(fake_hermes, tmp_path, monkeypatch):
    _scaffold(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("hpk.wizard._has_local_bin_on_path", lambda: True)

    def _explode(*a, **kw):
        raise AssertionError("interactive prompt called during --non-interactive run")

    from hpk import wizard

    monkeypatch.setattr(wizard, "_prompt_secret", _explode)
    monkeypatch.setattr(wizard, "_ask_plugin", _explode)
    monkeypatch.setattr("questionary.password", _explode)
    monkeypatch.setattr("questionary.confirm", _explode)

    (tmp_path / "tokens.env").write_text(
        "# slack creds for this workspace\n"
        f"SLACK_BOT_TOKEN={_BOT}\n"
        f"SLACK_SIGNING_SECRET={_SIGN}\n"
        f"SLACK_APP_TOKEN={_APP}\n"
    )

    r = CliRunner().invoke(
        cli_main,
        [
            "setup",
            "seb",
            "--non-interactive",
            "--env-file",
            str(tmp_path / "tokens.env"),
            "--accept-plugin",
            "codex-openai-proxy",
        ],
    )
    assert r.exit_code == 0, r.output
    env = (tmp_path / ".hermes" / "profiles" / "seb" / ".env").read_text()
    assert f"SLACK_BOT_TOKEN={_BOT}" in env
    assert "OPENAI_BASE_URL=http://localhost:8765/v1" in env  # manifest default applied
