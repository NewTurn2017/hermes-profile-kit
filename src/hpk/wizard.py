"""Interactive setup wizard. Phases: preflight → for each profile (A base, B tokens, C plugins)."""

from __future__ import annotations

import os
from pathlib import Path

import questionary
from packaging.version import Version

from hpk import hermes, profiles, tokens, ui
from hpk import plugins as plugins_mod
from hpk.manifest import Manifest, Plugin, Profile, TokenSpec
from hpk.tokens.base import TokenHandler


class PreflightError(RuntimeError):
    pass


class HermesNotInstalledError(PreflightError):
    pass


class HermesVersionTooOldError(PreflightError):
    pass


class NonInteractiveMissingError(PreflightError):
    """Required token value missing or invalid under --non-interactive."""

    def __init__(self, missing: list[str], invalid: list[tuple[str, str]] | None = None) -> None:
        invalid = invalid or []
        parts: list[str] = []
        if missing:
            parts.append("missing required tokens: " + ", ".join(missing))
        if invalid:
            parts.append("invalid token values: " + ", ".join(f"{k} ({why})" for k, why in invalid))
        if missing:
            suffix = " Re-run with --token KEY=VAL for each missing/invalid key."
        else:
            suffix = " Fix the value(s) and re-run."
        super().__init__("; ".join(parts) + "." + suffix)


class UnknownTokenKeyError(PreflightError):
    """`--token KEY=VAL` named a key the target profile does not declare."""


class UnknownPluginIdError(PreflightError):
    """`--accept-plugin`/`--reject-plugin` named an id not in recommended_plugins."""


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


def phase_b_tokens(
    profile: Profile,
    *,
    non_interactive: bool = False,
    token_overrides: dict[str, str] | None = None,
    env_file_values: dict[str, str] | None = None,
) -> None:
    ui.step(f"[B] tokens — {profile.name}")
    overrides = dict(token_overrides or {})
    env_values = dict(env_file_values or {})

    known_keys = {s.key for s in profile.tokens.required} | {s.key for s in profile.tokens.optional}
    for src_name, src in (("--token", overrides), ("--env-file", env_values)):
        unknown = sorted(set(src) - known_keys)
        if unknown:
            raise UnknownTokenKeyError(
                f"{src_name}: unknown key(s) for profile {profile.name!r}: {', '.join(unknown)}. "
                f"Valid: {', '.join(sorted(known_keys))}"
            )

    home = profiles.profile_home(profile.name)
    env_path = home / ".env"

    # Safety snapshot: if flags are about to mutate an existing .env, copy it to .env.bak first.
    # Interactive runs keep their current behavior (no snapshot).
    if env_path.exists() and (overrides or env_values):
        profiles.atomic_write(
            env_path.with_suffix(env_path.suffix + ".bak"),
            env_path.read_text(),
            mode=0o600,
        )

    missing: list[str] = []
    invalid_required: list[tuple[str, str]] = []

    for spec in profile.tokens.required:
        val = _resolve_value(spec, overrides=overrides, env_values=env_values)
        if val is not None:
            handler = _handler_for(spec)
            r = handler.validate(val)
            if not r.ok:
                invalid_required.append((spec.key, r.reason))
                continue
            profiles.set_env_key(env_path, spec.key, val)
            ui.ok(f"{spec.key} written")
            continue
        if non_interactive:
            if spec.default is not None:
                profiles.set_env_key(env_path, spec.key, spec.default)
                ui.ok(f"{spec.key} written (manifest default)")
            else:
                missing.append(spec.key)
            continue
        # interactive fallback (existing behavior)
        v = _collect_one(spec, optional=False)
        if v:
            profiles.set_env_key(env_path, spec.key, v)
            ui.ok(f"{spec.key} written")
        else:
            ui.warn(f"{spec.key} left as FILL_IN")

    if non_interactive and (missing or invalid_required):
        raise NonInteractiveMissingError(missing=missing, invalid=invalid_required)

    invalid_optional: list[tuple[str, str]] = []

    for spec in profile.tokens.optional:
        val = _resolve_value(spec, overrides=overrides, env_values=env_values)
        if val is not None:
            handler = _handler_for(spec)
            r = handler.validate(val)
            if not r.ok:
                if non_interactive:
                    invalid_optional.append((spec.key, r.reason))
                else:
                    ui.warn(f"{spec.key} invalid ({r.reason}) — left as-is")
                continue
            profiles.set_env_key(env_path, spec.key, val)
            ui.ok(f"{spec.key} written")
            continue
        if non_interactive:
            continue  # leave FILL_IN, no error for optional
        v = _collect_one(spec, optional=True)
        if v:
            profiles.set_env_key(env_path, spec.key, v)
            ui.ok(f"{spec.key} written")

    if non_interactive and invalid_optional:
        raise NonInteractiveMissingError(missing=[], invalid=invalid_optional)


def _resolve_value(
    spec: TokenSpec,
    *,
    overrides: dict[str, str],
    env_values: dict[str, str],
) -> str | None:
    """Precedence: --token (highest) > --env-file > None (caller applies manifest default)."""
    if spec.key in overrides:
        return overrides[spec.key]
    if spec.key in env_values:
        return env_values[spec.key]
    return None  # manifest default is applied later only under non-interactive


def _handler_for(spec: TokenSpec) -> TokenHandler:
    return (
        tokens.get_handler(provider=spec.provider, wizard=spec.wizard)
        if spec.wizard
        else tokens.get_handler(provider=spec.provider)
    )


def _ask_plugin(plugin_id: str, default: bool) -> bool:
    return bool(questionary.confirm(f"Enable plugin '{plugin_id}'?", default=default).ask())


def phase_c_plugins(
    profile: Profile,
    plugins_catalog: dict[str, Plugin],
    *,
    non_interactive: bool = False,
    accepted_plugins: set[str] | None = None,
    rejected_plugins: set[str] | None = None,
) -> None:
    accepted = set(accepted_plugins or ())
    rejected = set(rejected_plugins or ())

    known_ids = {rp.id for rp in profile.recommended_plugins}
    unknown_flagged = sorted((accepted | rejected) - known_ids)
    if unknown_flagged:
        raise UnknownPluginIdError(
            f"unknown plugin id(s) for profile {profile.name!r}: {', '.join(unknown_flagged)}. "
            f"Valid: {', '.join(sorted(known_ids)) or '(none)'}"
        )

    conflicts = accepted & rejected
    for pid in sorted(conflicts):
        ui.warn(f"plugin {pid}: both --accept-plugin and --reject-plugin given; reject wins")

    if not profile.recommended_plugins:
        return
    ui.step(f"[C] plugins — {profile.name}")
    for rp in profile.recommended_plugins:
        plugin = plugins_catalog.get(rp.id)
        if plugin is None:
            ui.warn(f"plugin {rp.id} not found in catalog — skipping")
            continue

        decision = _decide_plugin(
            rp_id=rp.id,
            default=rp.default,
            accepted=accepted,
            rejected=rejected,
            non_interactive=non_interactive,
        )
        if not decision:
            ui.ok(f"plugin {rp.id} skipped")
            continue

        # Kit-local helper: print install path, never exec hermes.
        if plugin.install_path and not plugin.verified_in_upstream:
            ui.warn(
                f"plugin [bold]{rp.id}[/bold] is a kit-local helper. "
                f"Install manually: see [cyan]{plugin.install_path}/README.md[/cyan]"
            )
            if plugin.launchd_template:
                ui.console.print(f"  launchd template: {plugin.launchd_template}")
            continue

        if not plugin.verified_in_upstream:
            ui.warn(f"plugin {rp.id} not verified — skipping")
            continue
        try:
            plugins_mod.run_plugin(plugin, profile=profile.name)
            ui.ok(f"plugin {rp.id} enabled")
        except plugins_mod.PluginExecError as e:
            ui.warn(f"plugin {rp.id} failed: {e}")


def _decide_plugin(
    *,
    rp_id: str,
    default: bool,
    accepted: set[str],
    rejected: set[str],
    non_interactive: bool,
) -> bool:
    if rp_id in rejected:
        return False
    if rp_id in accepted:
        return True
    if non_interactive:
        return default
    return _ask_plugin(rp_id, default)


def run_wizard(
    manifest: Manifest,
    *,
    targets: list[str],
    force: bool,
    skip_tokens: bool,
    skip_plugins: bool,
    non_interactive: bool = False,
    token_overrides: dict[str, str] | None = None,
    env_file_values: dict[str, str] | None = None,
    accepted_plugins: set[str] | None = None,
    rejected_plugins: set[str] | None = None,
) -> None:
    preflight(manifest)
    selected = [p for p in manifest.profiles if not targets or p.name in targets]
    for profile in selected:
        ui.header(f"profile {profile.name}")
        phase_a_base(profile, force=force)
        if not skip_tokens:
            phase_b_tokens(
                profile,
                non_interactive=non_interactive,
                token_overrides=token_overrides,
                env_file_values=env_file_values,
            )
        if not skip_plugins:
            phase_c_plugins(
                profile,
                manifest.plugins,
                non_interactive=non_interactive,
                accepted_plugins=accepted_plugins,
                rejected_plugins=rejected_plugins,
            )
