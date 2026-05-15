from hpk.tokens.base import TokenHandler, ValidationResult


class AnthropicHandler:
    key = "ANTHROPIC_API_KEY"
    provider = "anthropic"
    docs_url = "https://console.anthropic.com/settings/keys"

    def intro(self) -> str:
        return (
            "Anthropic API key.\n"
            f"  1. Open {self.docs_url}\n"
            "  2. Create a key (starts with sk-ant-)\n"
            "  3. Paste it below — input is hidden."
        )

    def validate(self, value: str) -> ValidationResult:
        if not value:
            return ValidationResult(False, "empty")
        if not value.startswith("sk-ant-"):
            return ValidationResult(False, "expected sk-ant- prefix")
        if len(value) < 20:
            return ValidationResult(False, "too short")
        return ValidationResult(True)


HANDLER: TokenHandler = AnthropicHandler()
