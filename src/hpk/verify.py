from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from hpk import hermes, profiles


def fill_in_findings(env_path: Path) -> Iterator[tuple[int, str]]:
    """Yield (lineno, key) for every FILL_IN_* placeholder in env_path."""
    if not env_path.exists():
        return
    for i, line in enumerate(env_path.read_text().splitlines(), 1):
        if "FILL_IN" in line and "=" in line:
            key = line.split("=", 1)[0]
            yield (i, key)


@dataclass
class VerifyResult:
    passing: list[str] = field(default_factory=list)
    failing: list[tuple[str, str]] = field(default_factory=list)  # (name, reason)
    fill_in_remaining: dict[str, list[tuple[int, str]]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.failing and not self.fill_in_remaining


def run_verify(profile_names: list[str]) -> VerifyResult:
    result = VerifyResult()
    for name in profile_names:
        env = profiles.profile_home(name) / ".env"
        rows = list(fill_in_findings(env))
        if rows:
            result.fill_in_remaining[name] = rows
        r = hermes.run_doctor(name)
        if r.returncode == 0:
            result.passing.append(name)
        else:
            result.failing.append((name, r.stderr.strip() or "doctor failed"))
    return result
