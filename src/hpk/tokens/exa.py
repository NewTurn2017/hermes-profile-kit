from hpk.tokens.base import ValidationResult


class ExaHandler:
    key = "EXA_API_KEY"
    provider = "exa"
    docs_url = "https://exa.ai/"

    def intro(self) -> str:
        return f"Exa API key from {self.docs_url}."

    def validate(self, value: str) -> ValidationResult:
        return ValidationResult(bool(value), "empty" if not value else "")
