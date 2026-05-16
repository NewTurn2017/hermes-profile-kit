"""JSON envelope helpers."""
from __future__ import annotations

import json
import sys
from typing import Any


def ok(**fields: Any) -> dict[str, Any]:
    return {"ok": True, **fields}


def err(code: int, kind: str, msg: str, hint: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"ok": False, "code": code, "kind": kind, "msg": msg}
    if hint is not None:
        body["hint"] = hint
    return body


def emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.write("\n")
