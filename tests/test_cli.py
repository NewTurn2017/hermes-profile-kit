from pathlib import Path

from click.testing import CliRunner

from hpk.cli import main


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
    (tmp_path / "manifest.yaml").write_text(
        open("tests/_fixtures/manifest_v2.yaml").read()
        if Path("tests/_fixtures/manifest_v2.yaml").exists()
        # inline a minimal manifest for the test
        else """schema_version: 2
kit: {name: hpk, version: 2.0.0, license: MIT}
upstream: {repo: x, pinned_commit: c, pinned_version: 0.12.3, verified_at: t}
min_hermes_version: 0.12.0
profiles: []
plugins: {}
preserve_existing: [.env]
overwrite_from_template: [SOUL.md, config.yaml]
"""
    )
    r = CliRunner().invoke(main, ["doctor"])
    assert r.exit_code == 0


def test_plugin_list_runs(fake_hermes, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "manifest.yaml").write_text(
        """schema_version: 2
kit: {name: hpk, version: 2.0.0, license: MIT}
upstream: {repo: x, pinned_commit: c, pinned_version: 0.12.3, verified_at: t}
min_hermes_version: 0.12.0
profiles: []
plugins: {}
preserve_existing: [.env]
overwrite_from_template: [SOUL.md, config.yaml]
"""
    )
    r = CliRunner().invoke(main, ["plugin", "list"])
    assert r.exit_code == 0
