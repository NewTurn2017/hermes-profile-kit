import pytest

from hpk.tokens import get_handler


def test_lookup_by_key():
    h = get_handler(provider="anthropic")
    assert h.key == "ANTHROPIC_API_KEY"


def test_lookup_by_wizard_id():
    h = get_handler(wizard="telegram_botfather")
    assert h.key == "TELEGRAM_BOT_TOKEN"


def test_unknown_raises():
    with pytest.raises(KeyError):
        get_handler(provider="ghost")
