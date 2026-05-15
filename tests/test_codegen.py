from hpk.codegen.argparse_walker import walk_argparse

TOY_MAIN = """
import argparse


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd")

    p_create = subparsers.add_parser("create", help="create a thing")
    p_create.add_argument("--name", required=True, help="thing name")

    p_profile = subparsers.add_parser("profile", help="profile ops")
    profile_subs = p_profile.add_subparsers(dest="op")

    p_create2 = profile_subs.add_parser("create2", help="create a profile")
    p_create2.add_argument("name")
    p_create2.add_argument("--clone-all", action="store_true")

    p_secret = profile_subs.add_parser("secret", help=argparse.SUPPRESS)
"""


def test_walk_extracts_commands_and_params():
    nodes = walk_argparse(TOY_MAIN)
    paths = {n["path"] for n in nodes}
    assert "create" in paths
    assert "profile create2" in paths
    assert "profile secret" in paths
    create2 = next(n for n in nodes if n["path"] == "profile create2")
    param_names = {p["name"] for p in create2["params"]}
    assert {"clone_all", "name"} <= param_names


def test_walk_marks_suppress_as_hidden():
    nodes = walk_argparse(TOY_MAIN)
    secret = next(n for n in nodes if n["path"] == "profile secret")
    assert secret["hidden"] is True
    create = next(n for n in nodes if n["path"] == "create")
    assert create["hidden"] is False
