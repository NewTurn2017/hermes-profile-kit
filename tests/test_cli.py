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
    assert r.exit_code == 0 and "2.0.0" in r.output


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
