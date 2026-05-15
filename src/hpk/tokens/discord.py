import re

from hpk.tokens.base import ValidationResult

_DISCORD_RE = re.compile(r"^[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{20,}$")


class DiscordHandler:
    key = "DISCORD_BOT_TOKEN"
    provider = "discord"
    docs_url = "https://discord.com/developers/applications"

    def intro(self) -> str:
        return (
            "Discord bot token.\n"
            f"  1. Open {self.docs_url}\n"
            "  2. New Application → Bot → Reset Token (copy once)\n"
            "  3. Paste below."
        )

    def validate(self, value: str) -> ValidationResult:
        if value.count(".") != 2:
            return ValidationResult(False, "expected 3 dot-separated segments")
        if not _DISCORD_RE.match(value):
            return ValidationResult(False, "shape does not match Discord token")
        return ValidationResult(True)


WIZARDS = {"discord_devportal": DiscordHandler()}
