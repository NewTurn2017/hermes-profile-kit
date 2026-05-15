import yaml

from scripts.update_manifest_pin import update_pin


def test_update_pin_writes_new_values(tmp_path):
    m = tmp_path / "manifest.yaml"
    m.write_text(
        """schema_version: 2
kit: {name: hpk, version: 2.0.0, license: MIT}
upstream: {repo: x, pinned_commit: old, pinned_version: 0.12.0, verified_at: old}
min_hermes_version: 0.12.0
profiles: []
plugins: {}
preserve_existing: [.env]
overwrite_from_template: [SOUL.md, config.yaml]
"""
    )
    update_pin(m, commit="new123", version="0.12.5", verified_at="2026-05-16T00:00Z")
    data = yaml.safe_load(m.read_text())
    assert data["upstream"]["pinned_commit"] == "new123"
    assert data["upstream"]["pinned_version"] == "0.12.5"
