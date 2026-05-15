from hpk.tokens.base import TokenHandler, ValidationResult


class SlackBotHandler:
    key = "SLACK_BOT_TOKEN"
    provider = "slack"
    docs_url = "https://api.slack.com/apps"

    def intro(self) -> str:
        return (
            "Slack Bot User OAuth Token (starts with xoxb-).\n"
            f"  1. Open {self.docs_url} and create a new app\n"
            "  2. Under 'OAuth & Permissions' install to a workspace\n"
            "  3. Copy 'Bot User OAuth Token' (xoxb-...)\n"
            "  4. Paste below."
        )

    def validate(self, value: str) -> ValidationResult:
        if not value.startswith("xoxb-"):
            return ValidationResult(False, "expected xoxb- prefix")
        return ValidationResult(True)


class SlackAppHandler:
    key = "SLACK_APP_TOKEN"
    provider = "slack"
    docs_url = "https://api.slack.com/apps"

    def intro(self) -> str:
        return (
            "Slack App-Level Token (starts with xapp-, needed for Socket Mode).\n"
            f"  1. {self.docs_url} → your app → 'Basic Information'\n"
            "  2. Under 'App-Level Tokens' click Generate\n"
            "  3. Scope: connections:write\n"
            "  4. Copy and paste below."
        )

    def validate(self, value: str) -> ValidationResult:
        if not value.startswith("xapp-"):
            return ValidationResult(False, "expected xapp- prefix")
        return ValidationResult(True)


WIZARDS: dict[str, TokenHandler] = {
    "slack_bot": SlackBotHandler(),
    "slack_app": SlackAppHandler(),
}
