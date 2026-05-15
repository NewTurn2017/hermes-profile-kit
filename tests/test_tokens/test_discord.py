from hpk.tokens.discord import DiscordHandler


def test_discord_format():
    # Discord bot tokens are 3 dot-separated b64 segments
    assert DiscordHandler().validate("AbCdEf" + "X" * 14 + ".GhIjK." + "Y" * 20).ok


def test_discord_must_have_two_dots():
    assert not DiscordHandler().validate("nodots").ok
