"""E2E: hpk setup seb — schema v3, openai-codex tokens, kit-local plugin."""

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

_VALID_SLACK_BOT   = "xoxb-" + "0" * 30
_VALID_SLACK_SIGN  = "a" * 32         # 32-char hex
_VALID_SLACK_APP   = "xapp-" + "0" * 30


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


def test_e2e_seb_setup_happy_path(fake_hermes, tmp_path, monkeypatch):
    """Full setup: Slack tokens answered, OpenAI tokens use defaults, kit-local plugin announced."""
    _scaffold(tmp_path)
    monkeypatch.chdir(tmp_path)

    from hpk import wizard

    # Return valid values per prompt key; empty string for codex keys → use default.
    def _fake_prompt(intro: str, key: str) -> str:
        if key == "SLACK_BOT_TOKEN":
            return _VALID_SLACK_BOT
        if key == "SLACK_SIGNING_SECRET":
            return _VALID_SLACK_SIGN
        if key == "SLACK_APP_TOKEN":
            return _VALID_SLACK_APP
        return ""  # OPENAI_BASE_URL, OPENAI_API_KEY → defaults

    monkeypatch.setattr(wizard, "_prompt_secret", _fake_prompt)
    monkeypatch.setattr("hpk.wizard._has_local_bin_on_path", lambda: True)
    # phase_c: user says "yes" to codex-openai-proxy install notice
    monkeypatch.setattr(
        "questionary.confirm",
        lambda msg, default=True: type("A", (), {"ask": lambda self: True})(),
    )

    r = CliRunner().invoke(cli_main, ["setup", "seb"])
    assert r.exit_code == 0, r.output

    env = tmp_path / ".hermes" / "profiles" / "seb" / ".env"
    contents = env.read_text()
    assert f"SLACK_BOT_TOKEN={_VALID_SLACK_BOT}" in contents
    assert f"SLACK_SIGNING_SECRET={_VALID_SLACK_SIGN}" in contents
    assert f"SLACK_APP_TOKEN={_VALID_SLACK_APP}" in contents
    assert "OPENAI_BASE_URL=http://localhost:8765/v1" in contents
    assert "OPENAI_API_KEY=sk-codex-proxy-local" in contents

    # hermes was called to create the profile, NOT to install the kit-local proxy
    assert ["hermes", "profile", "create", "seb"] in fake_hermes.calls
    hermes_calls_str = str(fake_hermes.calls)
    assert "codex-openai-proxy" not in hermes_calls_str


def test_e2e_seb_setup_idempotent(fake_hermes, tmp_path, monkeypatch):
    """Running setup twice preserves the existing .env."""
    _scaffold(tmp_path)
    monkeypatch.chdir(tmp_path)

    from hpk import wizard

    def _fake_prompt(intro: str, key: str) -> str:
        return {
            "SLACK_BOT_TOKEN": _VALID_SLACK_BOT,
            "SLACK_SIGNING_SECRET": _VALID_SLACK_SIGN,
            "SLACK_APP_TOKEN": _VALID_SLACK_APP,
        }.get(key, "")

    monkeypatch.setattr(wizard, "_prompt_secret", _fake_prompt)
    monkeypatch.setattr("hpk.wizard._has_local_bin_on_path", lambda: True)
    monkeypatch.setattr(
        "questionary.confirm",
        lambda msg, default=True: type("A", (), {"ask": lambda self: True})(),
    )

    runner = CliRunner()
    runner.invoke(cli_main, ["setup", "seb"])
    runner.invoke(cli_main, ["setup", "seb"])  # second run

    env = (tmp_path / ".hermes" / "profiles" / "seb" / ".env").read_text()
    assert f"SLACK_BOT_TOKEN={_VALID_SLACK_BOT}" in env
