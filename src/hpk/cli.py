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


@main.command()
def doctor() -> None:
    """Check hpk's own health: hermes presence, manifest validity, codegen freshness."""
    manifest = _load()
    from hpk import hermes as _h

    try:
        v = _h.get_version()
        ui.ok(f"hermes {v}")
    except _h.HermesNotFoundError:
        ui.err("hermes not found")
        sys.exit(10)
    ui.ok(f"manifest valid; pinned to {manifest.upstream.pinned_commit}")


@main.command()
@click.argument("profile", nargs=-1)
@click.option("--yes", is_flag=True, help="Skip confirmation.")
@click.option("--backup", is_flag=True, help="Export profile before deleting.")
def reset(profile: tuple[str, ...], yes: bool, backup: bool) -> None:
    """Remove profiles created by this kit (never touches default ~/.hermes/)."""
    manifest = _load()
    names = list(profile) or [p.name for p in manifest.profiles]
    if not yes:
        click.confirm(f"Really delete profiles: {', '.join(names)}?", abort=True)
    from hpk import hermes as _h

    for n in names:
        if backup:
            _h.run_raw(["hermes", "profile", "export", n])
        _h.run_raw(["hermes", "profile", "delete", n, "--yes"])
        ui.ok(f"deleted {n}")


@main.group()
def plugin() -> None:
    """List, enable, or disable manifest-declared recommended plugins."""


@plugin.command("list")
def plugin_list() -> None:
    manifest = _load()
    for p in manifest.profiles:
        ids = [rp.id for rp in p.recommended_plugins]
        ui.console.print(f"  {p.name}: {ids or '(none)'}")


@plugin.command("enable")
@click.argument("profile")
@click.argument("plugin_id")
def plugin_enable(profile: str, plugin_id: str) -> None:
    manifest = _load()
    plugins_catalog = manifest.plugins
    if plugin_id not in plugins_catalog:
        ui.err(f"unknown plugin: {plugin_id}")
        sys.exit(40)
    from hpk import plugins as _p

    _p.run_plugin(plugins_catalog[plugin_id], profile=profile)
    ui.ok(f"enabled {plugin_id} for {profile}")


@plugin.command("disable")
@click.argument("profile")
@click.argument("plugin_id")
def plugin_disable(profile: str, plugin_id: str) -> None:
    ui.warn(f"manual disable required for {plugin_id} on {profile}; see plugin docs")


@main.command()
@click.option("--dry-run", is_flag=True)
def sync(dry_run: bool) -> None:
    """Local upstream-drift check (CI does it daily). Calls scripts/regen_docs.py --check."""
    del dry_run  # accepted but not yet wired through
    import subprocess as _sp

    cmd = [sys.executable, "scripts/regen_docs.py", "--check"]
    r = _sp.run(cmd)
    sys.exit(50 if r.returncode else 0)


main.add_command(verify_cmd, name="verify")
