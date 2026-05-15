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
