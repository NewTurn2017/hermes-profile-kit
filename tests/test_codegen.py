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


def test_serialize_roundtrip(tmp_path):
    from hpk.codegen.cmd_index import dump, load

    nodes = [{"path": "profile create", "params": [], "help": "h", "hidden": False}]
    p = tmp_path / "i.json"
    dump(nodes, p)
    assert load(p) == nodes


def test_validate_manifest_against_index():
    from hpk.codegen.validate import find_missing_commands
    from hpk.manifest import Plugin

    plugins = {
        "honcho": Plugin(
            description="d",
            upstream_command="hermes -p {profile} memory setup honcho",
            verified_in_upstream=True,
        )
    }
    index = [{"path": "-p memory setup honcho", "params": [], "help": "", "hidden": False}]
    missing = find_missing_commands(plugins, index)
    assert missing == []  # the index contains the matching path (modulo profile substitution)


def test_validate_detects_missing():
    from hpk.codegen.validate import find_missing_commands
    from hpk.manifest import Plugin

    plugins = {
        "x": Plugin(
            description="d",
            upstream_command="hermes nope rename",
            verified_in_upstream=True,
        )
    }
    missing = find_missing_commands(plugins, [])
    assert missing == ["x"]


def test_validate_token_boundary_no_substring_false_positive():
    from hpk.codegen.validate import find_missing_commands
    from hpk.manifest import Plugin

    # Existing index path is "honcho"; plugin command's last token is "honchoplus"
    # The old endswith logic would have matched; the new boundary-aware logic should not.
    plugins = {
        "plus": Plugin(
            description="d",
            upstream_command="hermes setup honchoplus",
            verified_in_upstream=True,
        )
    }
    index = [{"path": "setup honcho", "params": [], "help": "", "hidden": False}]
    missing = find_missing_commands(plugins, index)
    assert missing == ["plus"]


def test_validate_exact_match_still_works():
    from hpk.codegen.validate import find_missing_commands
    from hpk.manifest import Plugin

    plugins = {
        "ok": Plugin(
            description="d",
            upstream_command="hermes -p {profile} memory setup honcho",
            verified_in_upstream=True,
        )
    }
    index = [
        {
            "path": "-p memory setup honcho",
            "params": [],
            "help": "",
            "hidden": False,
        }
    ]
    assert find_missing_commands(plugins, index) == []
