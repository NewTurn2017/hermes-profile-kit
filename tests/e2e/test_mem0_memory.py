"""hpk-level integration: manifest registers mem0-memory; seb opts in as default:false."""
from __future__ import annotations

from pathlib import Path

import pytest

from hpk.manifest import load_manifest
from hpk.plugins import PluginExecError, run_plugin


@pytest.fixture
def manifest():
    return load_manifest(Path("manifest.yaml"))


def test_manifest_registers_mem0_memory_plugin(manifest):
    assert "mem0-memory" in manifest.plugins
    p = manifest.plugins["mem0-memory"]
    assert p.upstream_command is None
    assert p.install_path == "scripts/mem0-memory"
    assert p.verified_in_upstream is False


def test_plugin_runner_refuses_kit_local_mem0(manifest):
    p = manifest.plugins["mem0-memory"]
    with pytest.raises(PluginExecError, match="install manually"):
        run_plugin(p, profile="seb")


def test_seb_profile_lists_mem0_as_optional(manifest):
    seb = next(p for p in manifest.profiles if p.name == "seb")
    plugin_ids = [r.id for r in seb.recommended_plugins]
    assert "mem0-memory" in plugin_ids
    rec = next(r for r in seb.recommended_plugins if r.id == "mem0-memory")
    assert rec.default is False
