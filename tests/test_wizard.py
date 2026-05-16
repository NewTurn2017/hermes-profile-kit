import pytest

from hpk.manifest import Manifest
from hpk.wizard import HermesNotInstalledError, HermesVersionTooOldError, preflight


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
    with pytest.raises(HermesVersionTooOldError):
        preflight(_load_manifest())


def test_preflight_raises_when_hermes_missing(monkeypatch):
    import shutil

    monkeypatch.setattr(shutil, "which", lambda _: None)
    monkeypatch.setattr("hpk.wizard._has_local_bin_on_path", lambda: True)
    with pytest.raises(HermesNotInstalledError, match="not installed"):
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


def test_phase_b_uses_token_default_on_empty_input(fake_hermes, tmp_path, monkeypatch):
    """When user presses Enter (empty string), wizard writes token_spec.default."""
    home = tmp_path / ".hermes/profiles/seb"
    home.mkdir(parents=True)
    (home / ".env").write_text("OPENAI_API_KEY=FILL_IN_OPENAI_API_KEY\n")
    monkeypatch.setenv("HOME", str(tmp_path))

    from hpk import wizard
    from hpk.manifest import Profile, TokenSpec, TokensSection
    from hpk.tokens.base import ValidationResult

    class _FakeCodexKeyHandler:
        key = "OPENAI_API_KEY"
        provider = "openai-codex"
        docs_url = ""

        def intro(self) -> str:
            return ""

        def validate(self, value: str) -> ValidationResult:
            return ValidationResult(True)

    import hpk.tokens as _tokens_mod
    monkeypatch.setitem(_tokens_mod._BY_WIZARD, "codex_api_key", _FakeCodexKeyHandler())

    profile = Profile(
        name="seb",
        template="/tmp",
        role="second brain",
        model_tier="openai-codex",
        channels=["slack"],
        tokens=TokensSection(
            required=[
                TokenSpec(
                    key="OPENAI_API_KEY",
                    provider="openai-codex",
                    wizard="codex_api_key",
                    default="sk-codex-proxy-local",
                )
            ]
        ),
    )
    # Empty input — user presses Enter
    monkeypatch.setattr(wizard, "_prompt_secret", lambda intro, key: "")
    wizard.phase_b_tokens(profile)

    contents = (home / ".env").read_text()
    assert "OPENAI_API_KEY=sk-codex-proxy-local" in contents


def test_phase_c_kit_local_plugin_prints_instructions(fake_hermes, tmp_path, monkeypatch, capsys):
    """Kit-local plugins (install_path, not verified) should print instructions, not exec."""
    monkeypatch.setenv("HOME", str(tmp_path))
    from hpk import wizard
    from hpk.manifest import (
        Plugin,
        Profile,
        RecommendedPlugin,
        TokensSection,
    )

    plugin = Plugin(
        description="local proxy",
        upstream_command=None,
        install_path="scripts/codex-openai-proxy",
        launchd_template="scripts/codex-openai-proxy/launchd.plist.example",
        verified_in_upstream=False,
        docs="scripts/codex-openai-proxy/README.md",
    )
    profile = Profile(
        name="seb",
        template="/tmp",
        role="second brain",
        model_tier="openai-codex",
        channels=["slack"],
        tokens=TokensSection(),
        recommended_plugins=[RecommendedPlugin(id="codex-openai-proxy", default=True)],
    )
    # User says "yes" to installing
    def _yes_confirm(msg, default=True):
        return type("A", (), {"ask": lambda self: True})()

    monkeypatch.setattr("questionary.confirm", _yes_confirm)
    wizard.phase_c_plugins(profile, {"codex-openai-proxy": plugin})

    # Should NOT raise; should NOT call hermes
    assert not any("hermes" in str(call) for call in fake_hermes.calls)
