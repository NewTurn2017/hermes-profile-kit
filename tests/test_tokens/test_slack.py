from hpk.tokens.slack import SlackAppHandler, SlackBotHandler


def test_bot_token_prefix():
    assert SlackBotHandler().validate("xoxb-12345-abcdef").ok
    assert not SlackBotHandler().validate("xapp-12345-abcdef").ok


def test_app_token_prefix():
    assert SlackAppHandler().validate("xapp-1-A1234-xyz").ok
    assert not SlackAppHandler().validate("xoxb-12345").ok


def test_slack_signing_secret_handler_validates_hex():
    from hpk.tokens.slack import SlackSigningSecretHandler
    h = SlackSigningSecretHandler()
    assert h.validate("a" * 32).ok is True
    assert h.validate("0f" * 16).ok is True


def test_slack_signing_secret_rejects_wrong_length():
    from hpk.tokens.slack import SlackSigningSecretHandler
    h = SlackSigningSecretHandler()
    assert h.validate("abc").ok is False
    assert h.validate("a" * 31).ok is False


def test_slack_signing_secret_rejects_non_hex():
    from hpk.tokens.slack import SlackSigningSecretHandler
    h = SlackSigningSecretHandler()
    assert h.validate("z" * 32).ok is False


def test_slack_signing_wizard_registered():
    from hpk.tokens import get_handler
    h = get_handler(wizard="slack_signing")
    assert h.key == "SLACK_SIGNING_SECRET"
