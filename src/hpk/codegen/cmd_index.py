import json
from pathlib import Path
from typing import Any, cast


def dump(nodes: list[dict[str, Any]], path: Path) -> None:
    sorted_nodes = sorted(nodes, key=lambda n: n["path"])
    path.write_text(json.dumps(sorted_nodes, indent=2, sort_keys=True) + "\n")


def load(path: Path) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], json.loads(path.read_text()))
