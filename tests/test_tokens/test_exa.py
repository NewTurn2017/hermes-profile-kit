from hpk.tokens.exa import ExaHandler


def test_exa_nonempty():
    assert ExaHandler().validate("anything").ok


def test_exa_rejects_empty():
    assert not ExaHandler().validate("").ok
