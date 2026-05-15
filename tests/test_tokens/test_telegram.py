from hpk.tokens.telegram import TelegramBotFatherHandler


def test_valid_telegram_format():
    assert TelegramBotFatherHandler().validate("123456789:ABCDefGhIJK_LmNoPQRsTuVwXyZ012345abc").ok


def test_telegram_requires_colon():
    r = TelegramBotFatherHandler().validate("123456789ABCDEF")
    assert not r.ok and ":" in r.reason


def test_telegram_first_part_must_be_digits():
    r = TelegramBotFatherHandler().validate("abc:tokenpart")
    assert not r.ok
