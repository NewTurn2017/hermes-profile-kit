"""Shared fixtures. fake_hermes monkeypatches subprocess for predictable Hermes interaction."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any

import pytest


@dataclass
class FakeHermes:
    calls: list[list[str]] = field(default_factory=list)
    profiles_existing: set[str] = field(default_factory=set)
    version: str = "0.12.3"
    home: Path | None = None

    def add_existing(self, name: str) -> None:
        self.profiles_existing.add(name)

    def __call__(self, cmd: list[str], *_args: Any, **kw: Any) -> CompletedProcess[str]:
        self.calls.append(list(cmd))
        if cmd[:2] == ["hermes", "--version"]:
            return CompletedProcess(cmd, 0, stdout=f"Hermes Agent v{self.version}\n", stderr="")
        if cmd[:3] == ["hermes", "profile", "show"]:
            name = cmd[3]
            if name in self.profiles_existing:
                return CompletedProcess(cmd, 0, stdout=f"profile {name}\n", stderr="")
            return CompletedProcess(cmd, 1, stdout="", stderr="not found\n")
        if cmd[:3] == ["hermes", "profile", "create"]:
            name = cmd[3]
            self.profiles_existing.add(name)
            if self.home is not None:
                (self.home / ".hermes/profiles" / name).mkdir(parents=True, exist_ok=True)
            return CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:2] == ["hermes", "doctor"] or (cmd[:2] == ["hermes", "-p"] and cmd[3] == "doctor"):
            return CompletedProcess(cmd, 0, stdout="ok\n", stderr="")
        return CompletedProcess(cmd, 0, stdout="", stderr="")


@pytest.fixture
def fake_hermes(monkeypatch, tmp_path) -> FakeHermes:
    fh = FakeHermes(home=tmp_path)
    monkeypatch.setattr(subprocess, "run", fh)
    monkeypatch.setenv("HOME", str(tmp_path))
    return fh
