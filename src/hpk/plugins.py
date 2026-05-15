"""Recommended-plugin runner. Dispatches a manifest-declared hermes command per profile."""

from __future__ import annotations

import shlex

from hpk.hermes import run_raw
from hpk.manifest import Plugin


class PluginExecError(RuntimeError):
    pass


def render_command(plugin: Plugin, *, profile: str) -> list[str]:
    if plugin.upstream_command is None:
        raise PluginExecError(
            f"plugin has no upstream_command — it is a kit-local helper "
            f"(install_path={plugin.install_path!r}). "
            f"Install it manually; see {plugin.docs or 'plugin docs'}."
        )
    return shlex.split(plugin.upstream_command.format(profile=profile))


def run_plugin(plugin: Plugin, *, profile: str) -> None:
    if plugin.install_path and not plugin.verified_in_upstream:
        raise PluginExecError(
            f"plugin at {plugin.install_path!r} is a kit-local helper — "
            f"install manually. See {plugin.docs or plugin.install_path + '/README.md'}."
        )
    if not plugin.verified_in_upstream:
        raise PluginExecError(f"plugin not verified in upstream: {plugin.upstream_command!r}")
    cmd = render_command(plugin, profile=profile)
    r = run_raw(cmd)
    if r.returncode != 0:
        raise PluginExecError(f"plugin command failed ({r.returncode}): {r.stderr.strip()}")
