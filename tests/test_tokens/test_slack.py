from hpk.tokens.slack import SlackBotHandler, SlackAppHandler


def test_bot_token_prefix():
    assert SlackBotHandler().validate("xoxb-12345-abcdef").ok
    assert not SlackBotHandler().validate("xapp-12345-abcdef").ok


def test_app_token_prefix():
    assert SlackAppHandler().validate("xapp-1-A1234-xyz").ok
    assert not SlackAppHandler().validate("xoxb-12345").ok
