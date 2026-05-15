"""Regenerate build/cmd_index.json and docs/commands.md from an upstream hermes-agent clone.

Usage:
    python scripts/regen_docs.py --upstream /path/to/hermes-agent \
        --out build/cmd_index.json --docs docs/commands.md
    python scripts/regen_docs.py --check        # exits 1 if regen produces diffs

Reads hermes_cli/main.py statically (AST-walks argparse subparser calls) — never
imports or executes upstream code.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from hpk.codegen.argparse_walker import walk_argparse  # noqa: E402
from hpk.codegen.cmd_index import dump, load  # noqa: E402

AUTO_START = "<!-- AUTO-GENERATED — DO NOT EDIT below this line. -->"
AUTO_END = "<!-- END AUTO-GENERATED -->"


def _locate_upstream_main(upstream_path: Path) -> Path:
    """Return the Path to hermes_cli/main.py under an upstream clone."""
    candidate = upstream_path / "hermes_cli" / "main.py"
    if not candidate.exists():
        candidate = upstream_path / "src" / "hermes_cli" / "main.py"
    if not candidate.exists():
        raise FileNotFoundError(
            f"hermes_cli/main.py not found under {upstream_path} "
            "(tried hermes_cli/ and src/hermes_cli/)"
        )
    return candidate


def _render_md(nodes: list[dict[str, Any]], pinned_commit: str) -> str:
    lines = [
        AUTO_START,
        f"<!-- Regenerated against hermes-agent@{pinned_commit}. Do not edit by hand. -->",
        "",
        "## Verified hermes commands",
        "",
    ]
    for n in nodes:
        if n["hidden"]:
            continue
        params = " ".join(
            ("--" + p["name"].replace("_", "-")) if p["is_flag"] else f"<{p['name']}>"
            for p in n["params"]
        )
        lines.append(f"- `hermes {n['path']} {params}`".rstrip())
    lines.append("")
    lines.append(AUTO_END)
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream", type=Path)
    ap.add_argument("--out", type=Path, default=REPO / "build" / "cmd_index.json")
    ap.add_argument("--docs", type=Path, default=REPO / "docs" / "commands.md")
    ap.add_argument("--pinned-commit", default="unknown")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    upstream: Path | None = args.upstream
    out_path: Path = args.out
    docs_path: Path = args.docs
    pinned_commit: str = args.pinned_commit
    check: bool = args.check

    if upstream is None:
        if check and out_path.exists():
            print("--check requires --upstream; skipping (CI provides it)")
            return
        ap.error("--upstream required unless --check with existing index")

    main_py = _locate_upstream_main(upstream)
    nodes = walk_argparse(main_py.read_text())

    new_md = _render_md(nodes, pinned_commit)

    if check:
        old_index = load(out_path) if out_path.exists() else []
        if old_index != sorted(nodes, key=lambda n: n["path"]):
            print("cmd_index drift detected", file=sys.stderr)
            sys.exit(1)
        if docs_path.exists():
            existing = docs_path.read_text()
            generated_block = new_md.split(AUTO_START, 1)[1]
            if generated_block not in existing:
                print("docs/commands.md auto-section drift", file=sys.stderr)
                sys.exit(1)
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    dump(nodes, out_path)

    if docs_path.exists():
        existing = docs_path.read_text()
        before, _, _ = existing.partition(AUTO_START)
        after_marker = existing.partition(AUTO_END)
        rest = after_marker[2] if AUTO_END in existing else ""
        merged = before + new_md + rest
    else:
        merged = (
            "# Commands Reference\n\n" + new_md + "\n## Kit-specific notes (hand-written)\n\n"
            "- Commands not in the verified list above are never invoked by `hpk`.\n"
        )
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    docs_path.write_text(merged)


if __name__ == "__main__":
    main()
