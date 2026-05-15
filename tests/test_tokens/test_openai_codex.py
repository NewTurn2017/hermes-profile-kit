import pytest


def test_codex_base_url_accepts_localhost():
    from hpk.tokens.openai_codex import CodexBaseURLHandler
    h = CodexBaseURLHandler()
    assert h.validate("http://localhost:8765/v1").ok is True
    assert h.validate("https://my-proxy.local/v1").ok is True


def test_codex_base_url_rejects_non_url():
    from hpk.tokens.openai_codex import CodexBaseURLHandler
    h = CodexBaseURLHandler()
    assert h.validate("localhost:8765").ok is False
    assert h.validate("").ok is False


def test_codex_api_key_accepts_any_non_empty():
    from hpk.tokens.openai_codex import CodexAPIKeyHandler
    h = CodexAPIKeyHandler()
    assert h.validate("sk-codex-proxy-local").ok is True
    assert h.validate("anything").ok is True


def test_codex_api_key_rejects_empty():
    from hpk.tokens.openai_codex import CodexAPIKeyHandler
    h = CodexAPIKeyHandler()
    assert h.validate("").ok is False


def test_codex_base_url_wizard_registered():
    from hpk.tokens import get_handler
    h = get_handler(wizard="codex_base_url")
    assert h.key == "OPENAI_BASE_URL"


def test_codex_api_key_wizard_registered():
    from hpk.tokens import get_handler
    h = get_handler(wizard="codex_api_key")
    assert h.key == "OPENAI_API_KEY"


def test_openai_codex_provider_registered():
    from hpk.tokens import get_handler
    # provider-only lookup (no wizard) is not defined for openai-codex; wizard is required
    with pytest.raises(KeyError):
        get_handler(provider="openai-codex")
