"""Profile-home filesystem operations: atomic writes, template apply, .env seeding."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path


def profile_home(name: str) -> Path:
    return Path(os.environ["HOME"]) / ".hermes" / "profiles" / name


def atomic_write(target: Path, content: str, *, mode: int = 0o600) -> None:
    """Write content atomically: tmp + chmod + rename. POSIX-atomic."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(content)
    tmp.chmod(mode)
    tmp.replace(target)


def seed_env_if_absent(*, template: Path, target: Path) -> bool:
    """If target does not exist, copy template to it with 0600 perms. Return True iff seeded."""
    if target.exists():
        return False
    atomic_write(target, template.read_text(), mode=0o600)
    return True


_ENV_LINE = re.compile(r"^(?P<key>[A-Z_][A-Z0-9_]*)=.*$")


def set_env_key(path: Path, key: str, value: str) -> None:
    """Replace or append `key=value` in a dotenv-style file. Preserves other lines."""
    lines = path.read_text().splitlines() if path.exists() else []
    out: list[str] = []
    replaced = False
    for ln in lines:
        m = _ENV_LINE.match(ln)
        if m and m.group("key") == key:
            out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(ln)
    if not replaced:
        out.append(f"{key}={value}")
    atomic_write(path, "\n".join(out) + "\n", mode=0o600)


def apply_templates(*, template_dir: Path, profile_home: Path, force: bool) -> None:
    """Copy SOUL.md and config.yaml from template_dir into profile_home.

    Existing files are preserved unless force=True. Never touches .env.
    """
    for fname in ("SOUL.md", "config.yaml"):
        src = template_dir / fname
        if not src.exists():
            continue
        dst = profile_home / fname
        if dst.exists() and not force:
            continue
        shutil.copy2(src, dst)
