from hpk.tokens.anthropic import AnthropicHandler


def test_valid_key():
    h = AnthropicHandler()
    assert h.validate("sk-ant-api03-" + "A" * 80).ok


def test_invalid_prefix_rejected():
    h = AnthropicHandler()
    r = h.validate("sk-openai-1234")
    assert not r.ok and "prefix" in r.reason


def test_empty_rejected():
    h = AnthropicHandler()
    assert not h.validate("").ok
