from __future__ import annotations

import sys
from pathlib import Path

import click

from hpk import __version__, ui, verify, wizard
from hpk.manifest import Manifest, ManifestValidationError, load_manifest


def _manifest_path() -> Path:
    return Path.cwd() / "manifest.yaml"


def _load() -> Manifest:
    try:
        return load_manifest(_manifest_path())
    except ManifestValidationError as e:
        ui.err(f"manifest invalid: {e}")
        sys.exit(40)
    except FileNotFoundError:
        ui.err(f"manifest.yaml not found at {_manifest_path()}")
        sys.exit(40)


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="hpk")
@click.pass_context
def main(ctx: click.Context) -> None:
    """hpk — interactive multi-profile setup for Hermes Agent."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(setup)


@main.command()
@click.argument("profile", nargs=-1)
@click.option("--non-interactive", is_flag=True, help="Read tokens from env vars only.")
@click.option("--dry-run", is_flag=True, help="Show actions without changing state.")
@click.option("--force", is_flag=True, help="Overwrite SOUL.md/config.yaml even if present.")
@click.option("--skip-tokens", is_flag=True)
@click.option("--skip-plugins", is_flag=True)
def setup(
    profile: tuple[str, ...],
    non_interactive: bool,
    dry_run: bool,
    force: bool,
    skip_tokens: bool,
    skip_plugins: bool,
) -> None:
    """Interactive multi-profile setup."""
    del non_interactive, dry_run  # accepted but not yet wired through
    manifest = _load()
    try:
        wizard.run_wizard(
            manifest,
            targets=list(profile),
            force=force,
            skip_tokens=skip_tokens,
            skip_plugins=skip_plugins,
        )
    except wizard.PreflightError as e:
        ui.err(str(e))
        if "not installed" in str(e):
            sys.exit(10)
        if "min_hermes_version" in str(e):
            sys.exit(11)
        sys.exit(30)


@main.command()
@click.argument("profile", nargs=-1)
def verify_cmd(profile: tuple[str, ...]) -> None:
    """Run hermes doctor + FILL_IN scan."""
    manifest = _load()
    names = list(profile) or [p.name for p in manifest.profiles]
    r = verify.run_verify(names)
    for name in r.passing:
        ui.ok(f"{name}: doctor green")
    for name, reason in r.failing:
        ui.err(f"{name}: {reason}")
    for name, rows in r.fill_in_remaining.items():
        for line, key in rows:
            ui.warn(f"{name}/.env:{line}: {key} still FILL_IN")
    sys.exit(0 if r.ok else 30)


main.add_command(verify_cmd, name="verify")
