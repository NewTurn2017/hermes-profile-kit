"""End-to-end: invoke hpk.cli with a full v2 manifest and a fake hermes."""

from pathlib import Path

from click.testing import CliRunner

from hpk.cli import main as cli_main

MANIFEST_YAML = """\
schema_version: 2
kit: {name: hpk, version: 2.0.0, license: MIT}
upstream: {repo: x, pinned_commit: abc, pinned_version: 0.12.3, verified_at: 2026-05-15T09:49Z}
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


def _scaffold(tmp_path: Path) -> None:
    (tmp_path / "manifest.yaml").write_text(MANIFEST_YAML)
    tpl = tmp_path / "profiles" / "coder"
    tpl.mkdir(parents=True)
    (tpl / "SOUL.md").write_text("soul")
    (tpl / "config.yaml").write_text("cfg")
    (tpl / ".env.example").write_text("ANTHROPIC_API_KEY=FILL_IN_ANTHROPIC_API_KEY\n")


def test_e2e_setup_happy_path(fake_hermes, tmp_path, monkeypatch):
    _scaffold(tmp_path)
    monkeypatch.chdir(tmp_path)
    # Stub the wizard's prompts to provide a valid Anthropic-shaped key
    from hpk import wizard

    monkeypatch.setattr(wizard, "_prompt_secret", lambda intro, key: "sk-ant-test-" + "A" * 30)
    monkeypatch.setattr("hpk.wizard._has_local_bin_on_path", lambda: True)

    r = CliRunner().invoke(cli_main, ["setup"])
    assert r.exit_code == 0, r.output

    env = tmp_path / ".hermes" / "profiles" / "coder" / ".env"
    assert "ANTHROPIC_API_KEY=sk-ant-test-" in env.read_text()
    assert ["hermes", "profile", "create", "coder"] in fake_hermes.calls


def test_e2e_setup_is_idempotent(fake_hermes, tmp_path, monkeypatch):
    _scaffold(tmp_path)
    monkeypatch.chdir(tmp_path)
    from hpk import wizard

    monkeypatch.setattr(wizard, "_prompt_secret", lambda intro, key: "sk-ant-test-" + "A" * 30)
    monkeypatch.setattr("hpk.wizard._has_local_bin_on_path", lambda: True)

    runner = CliRunner()
    runner.invoke(cli_main, ["setup"])
    runner.invoke(cli_main, ["setup"])  # second run: no overwrite

    env = (tmp_path / ".hermes" / "profiles" / "coder" / ".env").read_text()
    # Should still contain a real key, not be reverted to FILL_IN
    assert "sk-ant-test-" in env
