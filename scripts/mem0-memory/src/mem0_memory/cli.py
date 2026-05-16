"""hpk-memory CLI — write paths (add, share-add)."""
from __future__ import annotations

from typing import Any

import click

from mem0_memory.output import emit, err, ok
from mem0_memory.store import ExtractorError, Store

# Replaceable in tests via monkeypatch
_memory_factory: Any = None


def _parse_meta(pairs: tuple[str, ...]) -> dict[str, str] | None:
    if not pairs:
        return None
    out: dict[str, str] = {}
    for p in pairs:
        if "=" not in p:
            raise ValueError(f"bad meta '{p}' (expected key=value)")
        k, v = p.split("=", 1)
        if not k:
            raise ValueError(f"bad meta '{p}' (empty key)")
        out[k] = v
    return out


def _store_for_profile(profile: str) -> Store:
    return Store(profile=profile, memory_factory=_memory_factory)


def _shared_store() -> Store:
    return Store(shared=True, memory_factory=_memory_factory)


def _first_id(add_result: dict[str, Any]) -> str | None:
    raw = add_result.get("raw_result") if isinstance(add_result, dict) else None
    if isinstance(raw, dict):
        items = raw.get("results") or []
        if items:
            return items[0].get("id")
    return None


@click.group()
def main() -> None:
    """hpk-memory — per-profile + shared memory for hermes-profile-kit."""


@main.command("add")
@click.option("--profile", required=False, help="Target profile (required)")
@click.option("--text", required=False, help="Fact text to remember (required)")
@click.option("--meta", multiple=True, help="key=value metadata, repeatable")
@click.option("--scope", default=None, help="(forbidden on add — use share-add for shared)")
@click.option("--user-id", default=None)
def add_cmd(profile: str | None, text: str | None, meta: tuple[str, ...], scope: str | None, user_id: str | None) -> None:
    if scope is not None:
        emit(err(1, "shared_write_forbidden",
                 "add --scope is not allowed; use 'hpk-memory share-add' for the shared pool",
                 hint="share-add"))
        raise SystemExit(1)
    if not profile:
        emit(err(1, "missing_arg", "--profile is required for add"))
        raise SystemExit(1)
    if not text or not text.strip():
        emit(err(1, "missing_arg", "--text is required for add (non-blank)"))
        raise SystemExit(1)
    try:
        meta_dict = _parse_meta(meta)
    except ValueError as e:
        emit(err(1, "bad_meta", str(e)))
        raise SystemExit(1)
    store = _store_for_profile(profile)
    try:
        result = store.add(text, user_id=user_id, meta=meta_dict)
    except ExtractorError as e:
        emit(err(10, "extractor_failed", str(e),
                 hint="raw text saved to raw_facts; query will still find it"))
        raise SystemExit(10)
    payload: dict[str, Any] = {"scope": "profile", "id": _first_id(result)}
    if meta_dict:
        payload["meta"] = meta_dict
    emit(ok(**payload))


@main.command("share-add")
@click.option("--text", required=False, help="Fact text to remember in the shared pool (required)")
@click.option("--meta", multiple=True, help="key=value metadata, repeatable")
def share_add_cmd(text: str | None, meta: tuple[str, ...]) -> None:
    if not text or not text.strip():
        emit(err(1, "missing_arg", "--text is required for share-add (non-blank)"))
        raise SystemExit(1)
    try:
        meta_dict = _parse_meta(meta)
    except ValueError as e:
        emit(err(1, "bad_meta", str(e)))
        raise SystemExit(1)
    store = _shared_store()
    try:
        result = store.add(text, meta=meta_dict)
    except ExtractorError as e:
        emit(err(10, "extractor_failed", str(e),
                 hint="raw text saved to raw_facts; query will still find it"))
        raise SystemExit(10)
    payload: dict[str, Any] = {"scope": "shared", "id": _first_id(result)}
    if meta_dict:
        payload["meta"] = meta_dict
    emit(ok(**payload))


if __name__ == "__main__":
    main()
