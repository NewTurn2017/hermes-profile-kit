"""Path resolution: ~/.hermes/profiles/<p>/memory and ~/.hermes/shared/memory."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from mem0_memory.paths import (
    hermes_home as hermes_home_fn,
    profile_memory_dir,
    shared_memory_dir,
)


def test_hermes_home_defaults_to_user_home(monkeypatch):
    monkeypatch.delenv("HERMES_HOME", raising=False)
    assert hermes_home_fn() == Path.home() / ".hermes"


def test_hermes_home_respects_env_override(hermes_home):
    assert hermes_home == Path(os.environ["HERMES_HOME"])
    assert hermes_home_fn() == hermes_home


def test_profile_memory_dir(hermes_home):
    p = profile_memory_dir("seb")
    assert p == hermes_home / "profiles" / "seb" / "memory"


def test_shared_memory_dir(hermes_home):
    p = shared_memory_dir()
    assert p == hermes_home / "shared" / "memory"
