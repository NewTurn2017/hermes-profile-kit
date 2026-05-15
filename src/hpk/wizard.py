"""Interactive setup wizard. Phases: preflight → for each profile (A base, B tokens, C plugins)."""

from __future__ import annotations

import os
from pathlib import Path

from packaging.version import Version

from hpk import hermes, ui
from hpk.manifest import Manifest


class PreflightError(RuntimeError):
    pass


def _has_local_bin_on_path() -> bool:
    target = str(Path.home() / ".local" / "bin")
    return target in os.environ.get("PATH", "").split(os.pathsep)


def preflight(manifest: Manifest) -> None:
    ui.header("hpk preflight")
    try:
        v = hermes.get_version()
    except hermes.HermesNotFoundError as e:
        raise PreflightError(f"hermes not installed: {e}") from e
    ui.ok(f"hermes {v} detected (manifest requires ≥ {manifest.min_hermes_version})")
    if Version(v) < Version(manifest.min_hermes_version):
        raise PreflightError(f"hermes {v} < min_hermes_version {manifest.min_hermes_version}")
    if not _has_local_bin_on_path():
        ui.warn("~/.local/bin not on PATH — profile aliases like 'coder' won't work")
    else:
        ui.ok("~/.local/bin on PATH")
    ui.ok(f"manifest verified (pinned to {manifest.upstream.pinned_commit})")
