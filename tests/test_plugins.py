import pytest

from hpk.manifest import Plugin
from hpk.plugins import PluginExecError, render_command, run_plugin


def test_render_command_substitutes_profile():
    p = Plugin(
        description="x",
        upstream_command="hermes -p {profile} memory setup honcho",
        verified_in_upstream=True,
    )
    assert render_command(p, profile="research") == [
        "hermes",
        "-p",
        "research",
        "memory",
        "setup",
        "honcho",
    ]


def test_run_plugin_invokes_hermes(fake_hermes):
    p = Plugin(
        description="x",
        upstream_command="hermes -p {profile} doctor",
        verified_in_upstream=True,
    )
    run_plugin(p, profile="coder")
    assert ["hermes", "-p", "coder", "doctor"] in fake_hermes.calls


def test_run_plugin_skips_unverified():
    p = Plugin(description="x", upstream_command="hermes nope", verified_in_upstream=False)
    with pytest.raises(PluginExecError, match="not verified"):
        run_plugin(p, profile="coder")
