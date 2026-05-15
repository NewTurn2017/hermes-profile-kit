"""Subprocess wrapper around the installed `hermes` binary.

Never imports hermes internals. Every interaction goes through subprocess so
the kit stays decoupled from upstream API changes.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Sequence


class HermesNotFoundError(RuntimeError):
    """`hermes` binary is not on PATH."""


class HermesVersionError(RuntimeError):
    """Installed hermes does not meet a required version constraint."""


def _run(cmd: Sequence[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    if shutil.which("hermes") is None:
        raise HermesNotFoundError("hermes binary not found on PATH")
    return subprocess.run(list(cmd), capture_output=True, text=True, check=check)


_VERSION_RE = re.compile(r"Hermes Agent v(\d+\.\d+\.\d+)")


def get_version() -> str:
    """Return the installed Hermes version as `X.Y.Z`."""
    r = _run(["hermes", "--version"])
    m = _VERSION_RE.search(r.stdout)
    if not m:
        raise HermesVersionError(f"unparseable version output: {r.stdout!r}")
    return m.group(1)


def profile_exists(name: str) -> bool:
    r = _run(["hermes", "profile", "show", name])
    return r.returncode == 0


def run_profile_create(name: str) -> subprocess.CompletedProcess[str]:
    return _run(["hermes", "profile", "create", name], check=True)


def run_doctor(profile: str | None = None) -> subprocess.CompletedProcess[str]:
    cmd: list[str] = ["hermes"]
    if profile is not None:
        cmd += ["-p", profile]
    cmd += ["doctor"]
    return _run(cmd)


def run_raw(cmd: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Escape hatch for plugins.py to invoke arbitrary verified hermes commands."""
    return _run(cmd)
