"""Produce a markdown drift report for the upstream-sync PR body."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast


def compute_diff(
    old: list[dict[str, Any]], new: list[dict[str, Any]]
) -> tuple[list[str], list[str]]:
    op = {n["path"] for n in old}
    np_ = {n["path"] for n in new}
    return sorted(np_ - op), sorted(op - np_)


def render_markdown(*, added: list[str], removed: list[str], old_sha: str, new_sha: str) -> str:
    lines = [f"## Upstream sync — hermes-agent {old_sha} → {new_sha}", ""]
    if added:
        lines += ["### Commands added", *[f"+ `hermes {p}`" for p in added], ""]
    if removed:
        lines += ["### Commands removed", *[f"- `hermes {p}`" for p in removed], ""]
    if not added and not removed:
        lines += ["No command surface changes."]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old-index", type=Path, required=True)
    ap.add_argument("--new-index", type=Path, required=True)
    ap.add_argument("--old-sha", required=True)
    ap.add_argument("--new-sha", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    old: list[dict[str, Any]] = (
        cast(list[dict[str, Any]], json.loads(a.old_index.read_text()))
        if a.old_index.exists()
        else []
    )
    new = cast(list[dict[str, Any]], json.loads(a.new_index.read_text()))
    added, removed = compute_diff(old, new)
    a.out.write_text(
        render_markdown(added=added, removed=removed, old_sha=a.old_sha, new_sha=a.new_sha)
    )


if __name__ == "__main__":
    main()
