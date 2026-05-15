"""Per-provider token collection handlers.

Each handler is a small class with two methods:
  - intro(): print docs/links so the user knows where to obtain the token
  - validate(value): return (ok: bool, reason: str) without echoing the value
"""
from hpk.tokens.base import TokenHandler  # noqa: F401
