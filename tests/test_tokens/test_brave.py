from hpk.tokens.brave import BraveHandler


def test_brave_nonempty():
    assert BraveHandler().validate("BSAanySearchToken123").ok


def test_brave_rejects_empty():
    assert not BraveHandler().validate("").ok
