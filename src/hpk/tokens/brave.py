from hpk.tokens.base import ValidationResult


class BraveHandler:
    key = "BRAVE_SEARCH_API_KEY"
    provider = "brave"
    docs_url = "https://brave.com/search/api/"

    def intro(self) -> str:
        return f"Brave Search API key from {self.docs_url}."

    def validate(self, value: str) -> ValidationResult:
        return ValidationResult(bool(value), "empty" if not value else "")
