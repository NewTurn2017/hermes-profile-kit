import pytest

from hpk.manifest import Manifest
from hpk.wizard import PreflightError, preflight


def _load_manifest() -> Manifest:
    import yaml

    from hpk.manifest import Manifest
    from tests.test_manifest import VALID_YAML

    return Manifest.model_validate(yaml.safe_load(VALID_YAML))


def test_preflight_passes(fake_hermes, monkeypatch):
    base = monkeypatch.tmp_path if hasattr(monkeypatch, "tmp_path") else "/tmp"
    monkeypatch.setenv("PATH", f"{base}/.local/bin:/usr/bin")
    # We bypass PATH check using monkeypatch on the inner function:
    monkeypatch.setattr("hpk.wizard._has_local_bin_on_path", lambda: True)
    preflight(_load_manifest())  # no raise


def test_preflight_rejects_old_hermes(monkeypatch, fake_hermes):
    fake_hermes.version = "0.10.0"
    monkeypatch.setattr("hpk.wizard._has_local_bin_on_path", lambda: True)
    with pytest.raises(PreflightError, match="min_hermes_version"):
        preflight(_load_manifest())


def test_phase_a_creates_profile_and_applies_templates(fake_hermes, tmp_path, monkeypatch):
    # Prep a template dir
    tpl = tmp_path / "profiles" / "coder"
    tpl.mkdir(parents=True)
    (tpl / "SOUL.md").write_text("soul")
    (tpl / "config.yaml").write_text("cfg")
    (tpl / ".env.example").write_text("ANTHROPIC_API_KEY=FILL_IN_ANTHROPIC_API_KEY\n")

    from hpk.manifest import Profile, TokenSpec, TokensSection

    profile = Profile(
        name="coder",
        template=str(tpl),
        role="dev",
        model_tier="sonnet",
        channels=["cli"],
        tokens=TokensSection(required=[TokenSpec(key="ANTHROPIC_API_KEY", provider="anthropic")]),
    )
    monkeypatch.setenv("HOME", str(tmp_path))

    from hpk.wizard import phase_a_base

    phase_a_base(profile, force=False)
    home = tmp_path / ".hermes/profiles/coder"
    assert (home / "SOUL.md").exists()
    assert (home / "config.yaml").exists()
    assert (home / ".env").exists()
    assert ["hermes", "profile", "create", "coder"] in fake_hermes.calls


def test_phase_b_required_token_written(fake_hermes, tmp_path, monkeypatch):
    home = tmp_path / ".hermes/profiles/coder"
    home.mkdir(parents=True)
    (home / ".env").write_text("ANTHROPIC_API_KEY=FILL_IN_ANTHROPIC_API_KEY\n")
    monkeypatch.setenv("HOME", str(tmp_path))

    from hpk.manifest import Profile, TokenSpec, TokensSection

    profile = Profile(
        name="coder",
        template="/tmp",
        role="d",
        model_tier="sonnet",
        channels=["cli"],
        tokens=TokensSection(required=[TokenSpec(key="ANTHROPIC_API_KEY", provider="anthropic")]),
    )

    # Stub prompt to return a valid Anthropic-shaped key
    from hpk import wizard

    monkeypatch.setattr(wizard, "_prompt_secret", lambda intro, key: "sk-ant-test-" + "A" * 30)

    wizard.phase_b_tokens(profile)
    contents = (home / ".env").read_text()
    assert "ANTHROPIC_API_KEY=sk-ant-test-" in contents


def test_phase_c_runs_recommended_plugin(fake_hermes, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from hpk.manifest import (
        KitMeta,
        Manifest,
        Plugin,
        Profile,
        RecommendedPlugin,
        Upstream,
    )

    m = Manifest(
        schema_version=2,
        kit=KitMeta(name="k", version="v", license="MIT"),
        upstream=Upstream(repo="r", pinned_commit="c", pinned_version="0.12.3", verified_at="t"),
        min_hermes_version="0.12.0",
        profiles=[
            Profile(
                name="research",
                template="/tmp",
                role="r",
                model_tier="opus",
                channels=["cli"],
                recommended_plugins=[RecommendedPlugin(id="honcho", default=True)],
            ),
        ],
        plugins={
            "honcho": Plugin(
                description="d",
                upstream_command="hermes -p {profile} memory setup honcho",
                verified_in_upstream=True,
            )
        },
        preserve_existing=[".env"],
        overwrite_from_template=["SOUL.md", "config.yaml"],
    )
    monkeypatch.setattr("hpk.wizard._ask_plugin", lambda plugin_id, default: True)
    from hpk.wizard import phase_c_plugins

    phase_c_plugins(m.profiles[0], m.plugins)
    assert ["hermes", "-p", "research", "memory", "setup", "honcho"] in fake_hermes.calls
