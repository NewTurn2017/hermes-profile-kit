from __future__ import annotations

from typing import Any

from hpk.manifest import Plugin


def _normalize_cmd(cmd: str) -> str:
    """Strip 'hermes ' prefix and '{profile}' substitution markers for comparison."""
    parts = [p for p in cmd.split() if p not in ("hermes", "{profile}")]
    return " ".join(parts)


def find_missing_commands(plugins: dict[str, Plugin], cmd_index: list[dict[str, Any]]) -> list[str]:
    """Return plugin ids whose upstream_command is not present in cmd_index."""
    paths = {n["path"] for n in cmd_index}
    missing: list[str] = []
    for pid, plugin in plugins.items():
        if plugin.upstream_command is None:
            # Kit-local plugins (install_path) have nothing to validate against upstream.
            continue
        normalized = _normalize_cmd(plugin.upstream_command)
        if not any(normalized.endswith(p) or p == normalized for p in paths):
            missing.append(pid)
    return missing
