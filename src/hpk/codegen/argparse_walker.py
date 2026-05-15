"""AST-walk a Python source string/file containing an argparse-based CLI and
produce a stable flat list of {path, params, help, hidden} nodes per (sub)command.

Used at CI time only. Handles the upstream hermes_cli/main.py shape:
- argparse.ArgumentParser() at module/function scope
- nested subparsers via parser.add_subparsers() then xxx.add_parser("name", ...)
- params via parser.add_argument("--flag", ...) or parser.add_argument("pos", ...)
- help=argparse.SUPPRESS marks command or argument as hidden
"""

from __future__ import annotations

import ast
from typing import Any


def _is_suppress(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "argparse"
        and node.attr == "SUPPRESS"
    )


def _str_kwarg(call: ast.Call, name: str) -> str | None:
    for kw in call.keywords:
        if (
            kw.arg == name
            and isinstance(kw.value, ast.Constant)
            and isinstance(kw.value.value, str)
        ):
            return kw.value.value
    return None


def _bool_kwarg(call: ast.Call, name: str) -> bool:
    for kw in call.keywords:
        if kw.arg == name and isinstance(kw.value, ast.Constant):
            return bool(kw.value.value)
    return False


def _str_action(call: ast.Call) -> str | None:
    for kw in call.keywords:
        if (
            kw.arg == "action"
            and isinstance(kw.value, ast.Constant)
            and isinstance(kw.value.value, str)
        ):
            return kw.value.value
    return None


def _has_suppress_help(call: ast.Call) -> bool:
    for kw in call.keywords:
        if kw.arg == "help" and _is_suppress(kw.value):
            return True
    return False


def _param_from_add_argument(call: ast.Call) -> dict[str, Any] | None:
    """Build a param dict from a parser.add_argument(...) call. Returns None if unparseable."""
    if not call.args or not isinstance(call.args[0], ast.Constant):
        return None
    first = call.args[0].value
    if not isinstance(first, str):
        return None
    is_option = first.startswith("-")
    name = first.lstrip("-").replace("-", "_")
    opts: list[str] = []
    for a in call.args:
        if isinstance(a, ast.Constant) and isinstance(a.value, str):
            opts.append(a.value)
    action = _str_action(call)
    return {
        "name": name,
        "opts": opts,
        "is_flag": is_option and action in ("store_true", "store_false"),
        "required": _bool_kwarg(call, "required"),
        "type": "STRING",
        "help": None if _has_suppress_help(call) else _str_kwarg(call, "help"),
        "hidden": _has_suppress_help(call),
    }


def walk_argparse(source: str) -> list[dict[str, Any]]:
    """Return a flat list of {path, params, help, hidden} for every leaf subparser.

    The root ArgumentParser is not emitted; only its (recursively) descendant
    subparsers register as nodes.
    """
    tree = ast.parse(source)

    parser_path: dict[str, str] = {}  # parser-var → its path ("" for root)
    subparsers_parent: dict[str, str] = {}  # subparsers-var → parent parser's path
    nodes: dict[str, dict[str, Any]] = {}  # parser-var → node dict
    order: list[str] = []  # discovery order of subparser-vars

    # Pass 1: discover parser/subparsers/sub-parser variables and collect nodes.
    for n in ast.walk(tree):
        if not isinstance(n, ast.Assign) or len(n.targets) != 1:
            continue
        target = n.targets[0]
        if not isinstance(target, ast.Name):
            continue
        var = target.id
        val = n.value
        if not isinstance(val, ast.Call) or not isinstance(val.func, ast.Attribute):
            continue
        func = val.func
        if not isinstance(func.value, ast.Name):
            continue
        attr = func.attr
        recv = func.value.id

        if attr == "ArgumentParser" and recv == "argparse":
            parser_path[var] = ""
            continue

        if attr == "add_subparsers" and recv in parser_path:
            subparsers_parent[var] = parser_path[recv]
            continue

        if attr == "add_parser" and recv in subparsers_parent:
            if not val.args or not isinstance(val.args[0], ast.Constant):
                continue
            cmd = val.args[0].value
            if not isinstance(cmd, str):
                continue
            parent = subparsers_parent[recv]
            path = f"{parent} {cmd}".strip()
            parser_path[var] = path
            nodes[var] = {
                "path": path,
                "params": [],
                "help": None if _has_suppress_help(val) else _str_kwarg(val, "help"),
                "hidden": _has_suppress_help(val),
            }
            order.append(var)

    # Pass 2: attach add_argument calls to their parser nodes.
    for n in ast.walk(tree):
        if not isinstance(n, ast.Expr) or not isinstance(n.value, ast.Call):
            continue
        call = n.value
        if not isinstance(call.func, ast.Attribute) or call.func.attr != "add_argument":
            continue
        if not isinstance(call.func.value, ast.Name):
            continue
        recv = call.func.value.id
        if recv not in nodes:
            continue
        param = _param_from_add_argument(call)
        if param is not None:
            nodes[recv]["params"].append(param)

    return [nodes[v] for v in order]
