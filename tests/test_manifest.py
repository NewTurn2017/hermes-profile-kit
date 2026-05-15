from pathlib import Path

import pytest

from hpk.manifest import (
    Manifest,
    ManifestValidationError,
    load_manifest,
)

VALID_YAML = """\
schema_version: 2
kit: { name: hpk, version: 2.0.0, license: MIT }
upstream:
  repo: https://github.com/NousResearch/hermes-agent
  pinned_commit: abc1234
  pinned_version: 0.12.3
  verified_at: 2026-05-15T09:49Z
min_hermes_version: 0.12.0
profiles:
  - name: coder
    template: profiles/coder
    role: dev
    model_tier: sonnet
    channels: [cli]
    tokens:
      required:
        - { key: ANTHROPIC_API_KEY, provider: anthropic }
      optional: []
    recommended_plugins: []
plugins: {}
preserve_existing: [.env]
overwrite_from_template: [SOUL.md, config.yaml]
"""


def write(tmp_path: Path, text: str) -> Path:
    f = tmp_path / "manifest.yaml"
    f.write_text(text)
    return f


def test_load_valid_manifest(tmp_path):
    m = load_manifest(write(tmp_path, VALID_YAML))
    assert isinstance(m, Manifest)
    assert m.profiles[0].name == "coder"
    assert m.profiles[0].tokens.required[0].key == "ANTHROPIC_API_KEY"


def test_schema_version_must_be_2(tmp_path):
    bad = VALID_YAML.replace("schema_version: 2", "schema_version: 99")
    with pytest.raises(ManifestValidationError):
        load_manifest(write(tmp_path, bad))


def test_min_version_must_be_le_pinned(tmp_path):
    bad = VALID_YAML.replace("min_hermes_version: 0.12.0", "min_hermes_version: 99.0.0")
    with pytest.raises(ManifestValidationError, match="min_hermes_version"):
        load_manifest(write(tmp_path, bad))


def test_unknown_plugin_id_referenced(tmp_path):
    bad = VALID_YAML.replace(
        "recommended_plugins: []",
        "recommended_plugins:\n      - { id: nope, default: true }",
    )
    with pytest.raises(ManifestValidationError, match="unknown plugin"):
        load_manifest(write(tmp_path, bad))


def test_yaml_syntax_error_raises_manifest_error(tmp_path):
    bad = tmp_path / "manifest.yaml"
    bad.write_text("schema_version: 2\n  : bad\n")
    with pytest.raises(ManifestValidationError):
        load_manifest(bad)


V1_YAML = """\
kit:
  name: hermes-profile-kit
  version: 1.0.0
  description: drop-in kit
profiles:
  - name: coder
    template: profiles/coder
    role: dev
    model_tier: sonnet
    channels: [cli]
    requires_secrets: [ANTHROPIC_API_KEY]
    optional_secrets: []
min_hermes_version: 0.12.0
"""


def test_migrate_v1_to_v2(tmp_path):
    from hpk.manifest import migrate_v1_yaml

    out = migrate_v1_yaml(
        V1_YAML,
        pinned_commit="abc1234",
        pinned_version="0.12.3",
        verified_at="2026-05-15T09:49Z",
    )
    assert out["schema_version"] == 2
    assert out["profiles"][0]["tokens"]["required"][0]["key"] == "ANTHROPIC_API_KEY"
    assert out["plugins"] == {}
