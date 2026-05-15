"""Per-provider token collection handlers."""

from hpk.tokens.anthropic import HANDLER as _anthropic
from hpk.tokens.base import TokenHandler
from hpk.tokens.brave import BraveHandler
from hpk.tokens.discord import WIZARDS as _discord_wizards
from hpk.tokens.exa import ExaHandler
from hpk.tokens.openai_codex import WIZARDS as _openai_codex_wizards
from hpk.tokens.slack import WIZARDS as _slack_wizards
from hpk.tokens.telegram import WIZARDS as _telegram_wizards

_BY_PROVIDER: dict[str, TokenHandler] = {
    "anthropic": _anthropic,
    "brave": BraveHandler(),
    "exa": ExaHandler(),
}
_BY_WIZARD: dict[str, TokenHandler] = {
    **_telegram_wizards,
    **_slack_wizards,
    **_discord_wizards,
    **_openai_codex_wizards,
}


def get_handler(*, provider: str | None = None, wizard: str | None = None) -> TokenHandler:
    if wizard is not None:
        return _BY_WIZARD[wizard]
    if provider is not None:
        return _BY_PROVIDER[provider]
    raise ValueError("need provider or wizard")
