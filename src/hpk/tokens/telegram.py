import re

from hpk.tokens.base import TokenHandler, ValidationResult

_TELEGRAM_RE = re.compile(r"^\d{6,12}:[A-Za-z0-9_-]{20,}$")


class TelegramBotFatherHandler:
    key = "TELEGRAM_BOT_TOKEN"
    provider = "telegram"
    docs_url = "https://t.me/BotFather"

    def intro(self) -> str:
        return (
            "Telegram bot token (via BotFather).\n"
            f"  1. Open {self.docs_url} in Telegram\n"
            "  2. Send `/newbot` and follow the prompts\n"
            "  3. BotFather replies with `<digits>:<alphanum>`\n"
            "  4. Paste that whole string below."
        )

    def validate(self, value: str) -> ValidationResult:
        if ":" not in value:
            return ValidationResult(False, "missing ':' separator")
        if not _TELEGRAM_RE.match(value):
            return ValidationResult(False, "expected <digits>:<alphanumeric>")
        return ValidationResult(True)


HANDLER: TokenHandler = TelegramBotFatherHandler()
WIZARDS = {"telegram_botfather": HANDLER}
