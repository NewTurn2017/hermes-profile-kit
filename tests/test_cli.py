from click.testing import CliRunner

from hpk.cli import main

MANIFEST_YAML_MIN = """schema_version: 2
kit: {name: hpk, version: 2.0.0, license: MIT}
upstream: {repo: x, pinned_commit: c, pinned_version: 0.12.3, verified_at: t}
min_hermes_version: 0.12.0
profiles: []
plugins: {}
preserve_existing: [.env]
overwrite_from_template: [SOUL.md, config.yaml]
"""

MANIFEST_YAML_MIN_WITH_PROFILE = """schema_version: 2
kit: {name: hpk, version: 2.0.0, license: MIT}
upstream: {repo: x, pinned_commit: c, pinned_version: 0.12.3, verified_at: t}
min_hermes_version: 0.12.0
profiles:
  - name: coder
    template: profiles/coder
    role: dev
    model_tier: sonnet
    channels: [cli]
    tokens: {required: [], optional: []}
    recommended_plugins: []
plugins: {}
preserve_existing: [.env]
overwrite_from_template: [SOUL.md, config.yaml]
"""


def test_version() -> None:
    r = CliRunner().invoke(main, ["--version"])
    assert r.exit_code == 0 and "3.0.0" in r.output


def test_setup_subcommand_exists() -> None:
    r = CliRunner().invoke(main, ["setup", "--help"])
    assert r.exit_code == 0 and "PROFILE" in r.output


def test_verify_subcommand_exists() -> None:
    r = CliRunner().invoke(main, ["verify", "--help"])
    assert r.exit_code == 0


def test_unknown_command() -> None:
    r = CliRunner().invoke(main, ["nope"])
    assert r.exit_code != 0


def test_doctor_runs(fake_hermes, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "manifest.yaml").write_text(MANIFEST_YAML_MIN)
    r = CliRunner().invoke(main, ["doctor"])
    assert r.exit_code == 0


def test_plugin_list_runs(fake_hermes, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "manifest.yaml").write_text(MANIFEST_YAML_MIN)
    r = CliRunner().invoke(main, ["plugin", "list"])
    assert r.exit_code == 0


def test_sync_without_upstream_exits_zero_with_guidance(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    r = CliRunner().invoke(main, ["sync"])
    assert r.exit_code == 0
    # Guidance includes "--upstream" reference
    assert "--upstream" in r.output


def test_reset_with_yes_deletes_profiles(fake_hermes, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "manifest.yaml").write_text(MANIFEST_YAML_MIN_WITH_PROFILE)
    r = CliRunner().invoke(main, ["reset", "coder", "--yes"])
    assert r.exit_code == 0
    assert ["hermes", "profile", "delete", "coder", "--yes"] in fake_hermes.calls


def test_plugin_enable_unknown_exits_40(fake_hermes, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "manifest.yaml").write_text(MANIFEST_YAML_MIN)
    r = CliRunner().invoke(main, ["plugin", "enable", "coder", "nope"])
    assert r.exit_code == 40
    assert "unknown plugin" in r.output


def test_verify_fill_in_remaining(fake_hermes, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "manifest.yaml").write_text(MANIFEST_YAML_MIN_WITH_PROFILE)
    fake_hermes.add_existing("coder")
    home = tmp_path / ".hermes" / "profiles" / "coder"
    home.mkdir(parents=True)
    (home / ".env").write_text("ANTHROPIC_API_KEY=FILL_IN_ANTHROPIC_API_KEY\n")
    r = CliRunner().invoke(main, ["verify", "coder"])
    assert r.exit_code == 30  # not ok because FILL_IN present
    assert "FILL_IN" in r.output


MANIFEST_YAML_SEB_MIN = """schema_version: 3
kit: {name: hpk, version: 3.0.0, license: MIT}
upstream: {repo: x, pinned_commit: c, pinned_version: 0.12.3, verified_at: t}
min_hermes_version: 0.12.0
profiles:
  - name: seb
    template: profiles/seb
    role: second brain
    model_tier: openai-codex
    channels: [slack]
    tokens:
      required:
        - { key: SLACK_BOT_TOKEN, provider: slack, wizard: slack_bot }
      optional: []
    recommended_plugins:
      - { id: codex-openai-proxy, default: true }
plugins:
  codex-openai-proxy:
    description: local
    upstream_command: null
    install_path: scripts/codex-openai-proxy
    verified_in_upstream: false
preserve_existing: [.env]
overwrite_from_template: [SOUL.md, config.yaml]
"""


def _scaffold_seb_min(tmp_path) -> None:
    (tmp_path / "manifest.yaml").write_text(MANIFEST_YAML_SEB_MIN)
    tpl = tmp_path / "profiles" / "seb"
    tpl.mkdir(parents=True)
    (tpl / "SOUL.md").write_text("soul")
    (tpl / "config.yaml").write_text("model:\n  default: openai/gpt-5.5\n")
    (tpl / ".env.example").write_text("SLACK_BOT_TOKEN=FILL_IN\n")


def test_setup_help_lists_non_interactive_flags() -> None:
    r = CliRunner().invoke(main, ["setup", "--help"])
    assert r.exit_code == 0
    for flag in (
        "--token",
        "--env-file",
        "--accept-plugin",
        "--reject-plugin",
        "--non-interactive",
    ):
        assert flag in r.output


def test_setup_non_interactive_missing_required_exits_20(fake_hermes, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _scaffold_seb_min(tmp_path)
    monkeypatch.setattr("hpk.wizard._has_local_bin_on_path", lambda: True)
    r = CliRunner().invoke(main, ["setup", "seb", "--non-interactive"])
    assert r.exit_code == 20, r.output
    assert "SLACK_BOT_TOKEN" in r.output


def test_setup_non_interactive_unknown_token_exits_40(fake_hermes, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _scaffold_seb_min(tmp_path)
    monkeypatch.setattr("hpk.wizard._has_local_bin_on_path", lambda: True)
    r = CliRunner().invoke(
        main,
        [
            "setup",
            "seb",
            "--non-interactive",
            "--token",
            "NOT_A_KEY=x",
            "--token",
            "SLACK_BOT_TOKEN=xoxb-" + "0" * 30,
        ],
    )
    assert r.exit_code == 40, r.output
    assert "NOT_A_KEY" in r.output


def test_setup_non_interactive_unknown_plugin_exits_40(fake_hermes, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _scaffold_seb_min(tmp_path)
    monkeypatch.setattr("hpk.wizard._has_local_bin_on_path", lambda: True)
    r = CliRunner().invoke(
        main,
        [
            "setup",
            "seb",
            "--non-interactive",
            "--token",
            "SLACK_BOT_TOKEN=xoxb-" + "0" * 30,
            "--accept-plugin",
            "ghost-plugin",
        ],
    )
    assert r.exit_code == 40, r.output
    assert "ghost-plugin" in r.output


def test_setup_token_with_empty_value_exits_40(fake_hermes, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _scaffold_seb_min(tmp_path)
    monkeypatch.setattr("hpk.wizard._has_local_bin_on_path", lambda: True)
    r = CliRunner().invoke(
        main,
        ["setup", "seb", "--non-interactive", "--token", "SLACK_BOT_TOKEN="],
    )
    assert r.exit_code == 40, r.output
    assert "empty" in r.output.lower() or "SLACK_BOT_TOKEN" in r.output


def test_setup_env_file_loaded_and_token_flag_wins(fake_hermes, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _scaffold_seb_min(tmp_path)
    monkeypatch.setattr("hpk.wizard._has_local_bin_on_path", lambda: True)
    bot_from_file = "xoxb-" + "f" * 30
    bot_from_flag = "xoxb-" + "9" * 30
    (tmp_path / "tokens.env").write_text(f"SLACK_BOT_TOKEN={bot_from_file}\n")
    r = CliRunner().invoke(
        main,
        [
            "setup",
            "seb",
            "--non-interactive",
            "--env-file",
            str(tmp_path / "tokens.env"),
            "--token",
            f"SLACK_BOT_TOKEN={bot_from_flag}",
        ],
    )
    assert r.exit_code == 0, r.output
    env = (tmp_path / ".hermes" / "profiles" / "seb" / ".env").read_text()
    assert bot_from_flag in env
    assert bot_from_file not in env
