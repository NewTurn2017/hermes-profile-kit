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
@click.option("--force", is_flag=True, help="Overwrite SOUL.md/config.yaml even if present.")
@click.option("--skip-tokens", is_flag=True)
@click.option("--skip-plugins", is_flag=True)
@click.option(
    "--token",
    "tokens_kv",
    multiple=True,
    metavar="KEY=VAL",
    help="Inject a token value without prompting. Repeatable.",
)
@click.option(
    "--env-file",
    "env_file_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Load KEY=VAL lines (# comments allowed). --token values take precedence.",
)
@click.option(
    "--accept-plugin",
    "accept_plugins",
    multiple=True,
    metavar="ID",
    help="Force-enable a recommended plugin. Repeatable.",
)
@click.option(
    "--reject-plugin",
    "reject_plugins",
    multiple=True,
    metavar="ID",
    help="Force-skip a recommended plugin. Repeatable. Beats --accept-plugin on conflict.",
)
@click.option(
    "--non-interactive",
    is_flag=True,
    help="Fail with exit 20 instead of prompting when a required value is missing.",
)
def setup(
    profile: tuple[str, ...],
    force: bool,
    skip_tokens: bool,
    skip_plugins: bool,
    tokens_kv: tuple[str, ...],
    env_file_path: Path | None,
    accept_plugins: tuple[str, ...],
    reject_plugins: tuple[str, ...],
    non_interactive: bool,
) -> None:
    """Interactive multi-profile setup. See README's '2-minute install' for non-interactive use."""
    manifest = _load()

    token_overrides: dict[str, str] = {}
    for kv in tokens_kv:
        if "=" not in kv:
            ui.err(f"--token expects KEY=VAL, got: {kv!r}")
            sys.exit(40)
        key, _, val = kv.partition("=")
        token_overrides[key] = val

    env_file_values: dict[str, str] = {}
    if env_file_path is not None:
        from hpk.env_file import EnvFileParseError, load_env_file

        try:
            env_file_values = load_env_file(env_file_path)
        except EnvFileParseError as e:
            ui.err(str(e))
            sys.exit(40)

    try:
        wizard.run_wizard(
            manifest,
            targets=list(profile),
            force=force,
            skip_tokens=skip_tokens,
            skip_plugins=skip_plugins,
            non_interactive=non_interactive,
            token_overrides=token_overrides,
            env_file_values=env_file_values,
            accepted_plugins=set(accept_plugins),
            rejected_plugins=set(reject_plugins),
        )
    except wizard.HermesNotInstalledError as e:
        ui.err(str(e))
        sys.exit(10)
    except wizard.HermesVersionTooOldError as e:
        ui.err(str(e))
        sys.exit(11)
    except wizard.NonInteractiveMissingError as e:
        ui.err(str(e))
        sys.exit(20)
    except (wizard.UnknownTokenKeyError, wizard.UnknownPluginIdError) as e:
        ui.err(str(e))
        sys.exit(40)
    except wizard.PreflightError as e:
        ui.err(str(e))
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
@click.option(
    "--upstream",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Path to a local hermes-agent clone. Without it, sync prints guidance and exits.",
)
@click.option("--dry-run", is_flag=True, help="Run --check mode (no writes).")
def sync(upstream: Path | None, dry_run: bool) -> None:
    """Local upstream-drift check (CI does it daily). Requires an upstream clone."""
    import subprocess as _sp

    if upstream is None:
        ui.warn("hpk sync needs --upstream PATH (a local hermes-agent clone).")
        ui.warn("CI's daily upstream-sync workflow does this automatically.")
        sys.exit(0)
    cmd = [sys.executable, "scripts/regen_docs.py", "--upstream", str(upstream)]
    if dry_run:
        cmd.append("--check")
    r = _sp.run(cmd)
    sys.exit(50 if r.returncode else 0)


main.add_command(verify_cmd, name="verify")
