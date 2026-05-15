"""Token handlers for the openai-codex provider (local Codex CLI OAuth proxy)."""

from __future__ import annotations

from hpk.tokens.base import TokenHandler, ValidationResult


class CodexBaseURLHandler:
    """Handler for OPENAI_BASE_URL — the base URL of the local Codex proxy."""

    key = "OPENAI_BASE_URL"
    provider = "openai-codex"
    docs_url = "scripts/codex-openai-proxy/README.md"

    def intro(self) -> str:
        return (
            "Base URL for the local Codex OpenAI-compatible proxy.\n"
            "  Default: http://localhost:8765/v1\n"
            "  Start the proxy first:\n"
            "    cd scripts/codex-openai-proxy && uv run uvicorn proxy:app\n"
            "  Press Enter to accept the default."
        )

    def validate(self, value: str) -> ValidationResult:
        if not (value.startswith("http://") or value.startswith("https://")):
            return ValidationResult(False, "expected http:// or https:// URL")
        return ValidationResult(True)


class CodexAPIKeyHandler:
    """Handler for OPENAI_API_KEY — a dummy key accepted by the local proxy."""

    key = "OPENAI_API_KEY"
    provider = "openai-codex"
    docs_url = "scripts/codex-openai-proxy/README.md"

    def intro(self) -> str:
        return (
            "Dummy API key for the local Codex proxy.\n"
            "  Real authentication is via your logged-in 'codex' CLI session.\n"
            "  The OpenAI SDK requires this field to be non-empty.\n"
            "  Press Enter to accept the default: sk-codex-proxy-local"
        )

    def validate(self, value: str) -> ValidationResult:
        if not value:
            return ValidationResult(False, "value must not be empty — press Enter to use default")
        return ValidationResult(True)


WIZARDS: dict[str, TokenHandler] = {
    "codex_base_url": CodexBaseURLHandler(),
    "codex_api_key": CodexAPIKeyHandler(),
}
