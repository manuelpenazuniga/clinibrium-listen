"""PII redaction before any LLM call (SPECS §7 redact.py, L9).

Chilean RUT, phone numbers, e-mails and long digit runs → `[REDACTED]`.
Pure and idempotent: `redact(redact(x)) == redact(x)`.
"""
from __future__ import annotations

import re

REDACTED = "[REDACTED]"

_PATTERNS: tuple[re.Pattern[str], ...] = (
    # e-mail
    re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
    # Chilean RUT: 12.345.678-9 / 12345678-K / 1.234.567-8
    re.compile(r"\b\d{1,2}(?:\.?\d{3}){2}\s*-\s*[\dkK]\b"),
    # phones: +56 9 1234 5678, 56912345678, 9 1234 5678, (2) 2345 6789
    re.compile(r"(?:\+?56[\s-]?)?(?:\(?\d\)?[\s-]?)?\d{4}[\s-]?\d{4}\b"),
    # any remaining long digit run (IDs, record numbers)
    re.compile(r"\d{7,}"),
)


def redact(text: str) -> str:
    out = text
    for pat in _PATTERNS:
        out = pat.sub(REDACTED, out)
    return out


__all__ = ["REDACTED", "redact"]
