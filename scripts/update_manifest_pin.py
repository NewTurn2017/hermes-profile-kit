"""Update manifest.yaml's upstream.pinned_* fields. Called by upstream-sync workflow."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, cast

import yaml


def update_pin(path: Path, *, commit: str, version: str, verified_at: str) -> None:
    data = cast(dict[str, Any], yaml.safe_load(path.read_text()))
    data["upstream"]["pinned_commit"] = commit
    data["upstream"]["pinned_version"] = version
    data["upstream"]["verified_at"] = verified_at
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=Path("manifest.yaml"))
    ap.add_argument("--commit", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--verified-at", required=True)
    a = ap.parse_args()
    update_pin(a.manifest, commit=a.commit, version=a.version, verified_at=a.verified_at)


if __name__ == "__main__":
    main()
