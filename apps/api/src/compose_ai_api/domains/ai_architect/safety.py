from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
INJECTION_PATTERNS = (
    re.compile(
        r"ignore\s+(?:all\s+)?(?:(?:previous|prior)\s+)?"
        r"(?:system\s+|developer\s+)?instructions",
        re.IGNORECASE,
    ),
    re.compile(r"reveal\s+(?:the\s+)?(?:system|developer)\s+prompt", re.IGNORECASE),
    re.compile(r"act\s+as\s+(?:the\s+)?system", re.IGNORECASE),
)


@dataclass(frozen=True)
class RedactionResult:
    provider_text: str
    redacted_email_count: int
    redacted_phone_count: int
    injection_signals: tuple[str, ...]


def prepare_untrusted_text(value: str) -> RedactionResult:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = "".join(
        character
        for character in normalized
        if character in "\n\t" or unicodedata.category(character) != "Cc"
    )
    email_count = len(EMAIL_PATTERN.findall(normalized))
    provider_text = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", normalized)
    phone_count = len(PHONE_PATTERN.findall(provider_text))
    provider_text = PHONE_PATTERN.sub("[REDACTED_PHONE]", provider_text)
    signals = tuple(
        pattern.pattern for pattern in INJECTION_PATTERNS if pattern.search(provider_text)
    )
    return RedactionResult(
        provider_text=provider_text,
        redacted_email_count=email_count,
        redacted_phone_count=phone_count,
        injection_signals=signals,
    )
