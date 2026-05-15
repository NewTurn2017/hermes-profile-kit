"""Recommended-plugin runner. Dispatches a manifest-declared hermes command per profile."""

from __future__ import annotations

import shlex

from hpk.hermes import run_raw
from hpk.manifest import Plugin


class PluginExecError(RuntimeError):
    pass


def render_command(plugin: Plugin, *, profile: str) -> list[str]:
    return shlex.split(plugin.upstream_command.format(profile=profile))


def run_plugin(plugin: Plugin, *, profile: str) -> None:
    if not plugin.verified_in_upstream:
        raise PluginExecError(f"plugin not verified in upstream: {plugin.upstream_command!r}")
    cmd = render_command(plugin, profile=profile)
    r = run_raw(cmd)
    if r.returncode != 0:
        raise PluginExecError(f"plugin command failed ({r.returncode}): {r.stderr.strip()}")
