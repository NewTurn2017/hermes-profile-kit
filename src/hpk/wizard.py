"""Interactive setup wizard. Phases: preflight → for each profile (A base, B tokens, C plugins)."""

from __future__ import annotations

import os
from pathlib import Path

import questionary
from packaging.version import Version

from hpk import hermes, profiles, tokens, ui
from hpk import plugins as plugins_mod
from hpk.manifest import Manifest, Plugin, Profile, TokenSpec


class PreflightError(RuntimeError):
    pass


class HermesNotInstalledError(PreflightError):
    pass


class HermesVersionTooOldError(PreflightError):
    pass


def _has_local_bin_on_path() -> bool:
    target = str(Path.home() / ".local" / "bin")
    return target in os.environ.get("PATH", "").split(os.pathsep)


def preflight(manifest: Manifest) -> None:
    ui.header("hpk preflight")
    try:
        v = hermes.get_version()
    except hermes.HermesNotFoundError as e:
        raise HermesNotInstalledError(f"hermes not installed: {e}") from e
    ui.ok(f"hermes {v} detected (manifest requires ≥ {manifest.min_hermes_version})")
    if Version(v) < Version(manifest.min_hermes_version):
        raise HermesVersionTooOldError(
            f"hermes {v} < min_hermes_version {manifest.min_hermes_version}"
        )
    if not _has_local_bin_on_path():
        ui.warn("~/.local/bin not on PATH — profile aliases like 'coder' won't work")
    else:
        ui.ok("~/.local/bin on PATH")
    ui.ok(f"manifest verified (pinned to {manifest.upstream.pinned_commit})")


def phase_a_base(profile: Profile, *, force: bool) -> None:
    ui.step(f"[A] base — {profile.name}")
    if not hermes.profile_exists(profile.name):
        hermes.run_profile_create(profile.name)
        ui.ok(f"hermes profile create {profile.name}")
    else:
        ui.ok(f"profile '{profile.name}' already exists — skip create")

    home = profiles.profile_home(profile.name)
    home.mkdir(parents=True, exist_ok=True)
    profiles.apply_templates(
        template_dir=Path(profile.template),
        profile_home=home,
        force=force,
    )
    ui.ok("templates applied (SOUL.md, config.yaml)")
    seeded = profiles.seed_env_if_absent(
        template=Path(profile.template) / ".env.example",
        target=home / ".env",
    )
    ui.ok(".env seeded" if seeded else ".env preserved")


def _prompt_secret(intro: str, key: str) -> str:
    ui.console.print(intro)
    answer = questionary.password(f"  {key}").ask()
    return str(answer) if answer else ""


def _collect_one(token_spec: TokenSpec, *, optional: bool) -> str | None:
    handler = (
        tokens.get_handler(provider=token_spec.provider, wizard=token_spec.wizard)
        if token_spec.wizard
        else tokens.get_handler(provider=token_spec.provider)
    )
    if optional:
        proceed = questionary.confirm(
            f"Set up {token_spec.provider} ({token_spec.key}) now?", default=False
        ).ask()
        if not proceed:
            return token_spec.default  # return default instead of None
    for attempt in range(3):
        value = _prompt_secret(handler.intro(), token_spec.key)
        if not value:
            return token_spec.default  # return default instead of None
        r = handler.validate(value)
        if r.ok:
            return value
        ui.warn(f"validation failed: {r.reason} (attempt {attempt + 1}/3)")
    ui.warn("3 failed validations — skipping")
    return token_spec.default  # return default instead of None


def phase_b_tokens(profile: Profile) -> None:
    ui.step(f"[B] tokens — {profile.name}")
    home = profiles.profile_home(profile.name)
    env_path = home / ".env"
    for spec in profile.tokens.required:
        val = _collect_one(spec, optional=False)
        if val:
            profiles.set_env_key(env_path, spec.key, val)
            ui.ok(f"{spec.key} written")
        else:
            ui.warn(f"{spec.key} left as FILL_IN")
    for spec in profile.tokens.optional:
        val = _collect_one(spec, optional=True)
        if val:
            profiles.set_env_key(env_path, spec.key, val)
            ui.ok(f"{spec.key} written")


def _ask_plugin(plugin_id: str, default: bool) -> bool:
    return bool(questionary.confirm(f"Enable plugin '{plugin_id}'?", default=default).ask())


def phase_c_plugins(profile: Profile, plugins_catalog: dict[str, Plugin]) -> None:
    if not profile.recommended_plugins:
        return
    ui.step(f"[C] plugins — {profile.name}")
    for rp in profile.recommended_plugins:
        plugin = plugins_catalog.get(rp.id)
        if plugin is None:
            ui.warn(f"plugin {rp.id} not found in catalog — skipping")
            continue

        # Kit-local helper: print install path, never exec hermes.
        if plugin.install_path and not plugin.verified_in_upstream:
            if _ask_plugin(rp.id, rp.default):
                ui.warn(
                    f"plugin [bold]{rp.id}[/bold] is a kit-local helper. "
                    f"Install manually: see [cyan]{plugin.install_path}/README.md[/cyan]"
                )
                if plugin.launchd_template:
                    ui.console.print(f"  launchd template: {plugin.launchd_template}")
            else:
                ui.ok(f"plugin {rp.id} skipped by user")
            continue

        if not plugin.verified_in_upstream:
            ui.warn(f"plugin {rp.id} not verified — skipping")
            continue
        if not _ask_plugin(rp.id, rp.default):
            ui.ok(f"plugin {rp.id} skipped by user")
            continue
        try:
            plugins_mod.run_plugin(plugin, profile=profile.name)
            ui.ok(f"plugin {rp.id} enabled")
        except plugins_mod.PluginExecError as e:
            ui.warn(f"plugin {rp.id} failed: {e}")


def run_wizard(
    manifest: Manifest,
    *,
    targets: list[str],
    force: bool,
    skip_tokens: bool,
    skip_plugins: bool,
) -> None:
    preflight(manifest)
    selected = [p for p in manifest.profiles if not targets or p.name in targets]
    for profile in selected:
        ui.header(f"profile {profile.name}")
        phase_a_base(profile, force=force)
        if not skip_tokens:
            phase_b_tokens(profile)
        if not skip_plugins:
            phase_c_plugins(profile, manifest.plugins)
