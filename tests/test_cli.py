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
