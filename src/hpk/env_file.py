"""`KEY=VAL` file parser + key-level merge into an existing dotenv with `.env.bak` snapshot."""

from __future__ import annotations

import re
from pathlib import Path

from hpk.profiles import atomic_write, set_env_key


class EnvFileParseError(ValueError):
    """Raised when --env-file content cannot be parsed."""


_ENV_LINE = re.compile(r"^(?P<key>[A-Z_][A-Z0-9_]*)=(?P<val>.*)$")


def load_env_file(path: Path) -> dict[str, str]:
    """Parse a KEY=VAL file. `#` line comments and blank lines are allowed.

    Keys must match `[A-Z_][A-Z0-9_]*` (matches the dotenv convention used by
    `hpk.profiles.set_env_key`). Raises EnvFileParseError on the first
    malformed line, including the 1-based line number.
    """
    out: dict[str, str] = {}
    for i, raw in enumerate(path.read_text().splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _ENV_LINE.match(line)
        if not m:
            raise EnvFileParseError(f"{path}: line {i}: malformed env line: {raw!r}")
        out[m.group("key")] = m.group("val")
    return out


def merge_into_env(target: Path, values: dict[str, str]) -> None:
    """Update `target` so each KEY in `values` maps to its VAL. Other lines untouched.

    If `target` exists and contains content, write a snapshot to `target` + `.bak`
    *before* mutating, overwriting any previous backup. If `target` does not
    exist, create it (mode 0600) and skip the backup.
    """
    if target.exists():
        prior = target.read_text()
        atomic_write(target.with_suffix(target.suffix + ".bak"), prior, mode=0o600)
    for key, val in values.items():
        set_env_key(target, key, val)
