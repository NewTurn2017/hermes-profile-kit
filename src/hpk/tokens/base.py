from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: str = ""


class TokenHandler(Protocol):
    """Protocol every token-provider handler implements.

    Handlers must NEVER echo the token value. `validate` returns a reason
    string but must not include the value verbatim.
    """

    key: str
    provider: str
    docs_url: str

    def intro(self) -> str:
        """Markdown/plain text instructions shown before prompting."""
        ...

    def validate(self, value: str) -> ValidationResult:
        """Lightweight client-side format check. Network calls forbidden."""
        ...
