"""Path resolution for the mem0-memory plugin storage tree."""
from __future__ import annotations

import os
from pathlib import Path


def hermes_home() -> Path:
    """Return ~/.hermes, or $HERMES_HOME if set (used by tests)."""
    override = os.environ.get("HERMES_HOME")
    return Path(override) if override else Path.home() / ".hermes"


def profile_memory_dir(profile: str) -> Path:
    return hermes_home() / "profiles" / profile / "memory"


def shared_memory_dir() -> Path:
    return hermes_home() / "shared" / "memory"
