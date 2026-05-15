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


SEV3_YAML = """\
schema_version: 3
kit: { name: hpk, version: 3.0.0, license: MIT }
upstream:
  repo: https://github.com/NousResearch/hermes-agent
  pinned_commit: abc1234
  pinned_version: 0.12.3
  verified_at: 2026-05-15T09:49Z
min_hermes_version: 0.12.0
profiles:
  - name: seb
    template: profiles/seb
    role: second brain
    model_tier: openai-codex
    channels: [slack]
    tokens:
      required:
        - { key: SLACK_BOT_TOKEN, provider: slack, wizard: slack_bot }
        - { key: OPENAI_BASE_URL, provider: openai-codex,
            wizard: codex_base_url, default: "http://localhost:8765/v1" }
        - { key: OPENAI_API_KEY, provider: openai-codex,
            wizard: codex_api_key, default: "sk-codex-proxy-local" }
      optional: []
    recommended_plugins:
      - { id: codex-openai-proxy, default: true }
plugins:
  codex-openai-proxy:
    description: local proxy
    upstream_command: null
    install_path: scripts/codex-openai-proxy
    launchd_template: scripts/codex-openai-proxy/launchd.plist.example
    verified_in_upstream: false
    docs: scripts/codex-openai-proxy/README.md
preserve_existing: [.env]
overwrite_from_template: [SOUL.md, config.yaml]
"""


def test_schema_version_3_accepted(tmp_path):
    m = load_manifest(write(tmp_path, SEV3_YAML))
    assert m.schema_version == 3
    assert m.profiles[0].model_tier == "openai-codex"
    assert m.profiles[0].channels == ["slack"]


def test_token_spec_default_field(tmp_path):
    m = load_manifest(write(tmp_path, SEV3_YAML))
    base_url_spec = next(
        t for t in m.profiles[0].tokens.required if t.key == "OPENAI_BASE_URL"
    )
    assert base_url_spec.default == "http://localhost:8765/v1"


def test_plugin_nullable_upstream_command(tmp_path):
    m = load_manifest(write(tmp_path, SEV3_YAML))
    plugin = m.plugins["codex-openai-proxy"]
    assert plugin.upstream_command is None
    assert plugin.install_path == "scripts/codex-openai-proxy"
    assert plugin.launchd_template == "scripts/codex-openai-proxy/launchd.plist.example"


def test_schema_version_2_still_accepted(tmp_path):
    m = load_manifest(write(tmp_path, VALID_YAML))
    assert m.schema_version == 2


def test_unknown_schema_version_rejected(tmp_path):
    bad = SEV3_YAML.replace("schema_version: 3", "schema_version: 99")
    with pytest.raises(ManifestValidationError):
        load_manifest(write(tmp_path, bad))


def test_openai_codex_model_tier_accepted(tmp_path):
    m = load_manifest(write(tmp_path, SEV3_YAML))
    assert m.profiles[0].model_tier == "openai-codex"


def test_invalid_model_tier_rejected(tmp_path):
    bad = SEV3_YAML.replace("model_tier: openai-codex", "model_tier: gpt-99")
    with pytest.raises(ManifestValidationError):
        load_manifest(write(tmp_path, bad))
