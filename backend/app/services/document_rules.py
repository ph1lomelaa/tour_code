from __future__ import annotations

import re


_INVALID_TOKENS = {"DOCUMENT", "DOCUMENTNUMBER", "PASSPORT", "IIN", "ИИН"}


def normalize_document(value: str) -> str:
    cleaned = re.sub(r"[^\w]", "", str(value or "").upper().strip())
    if not cleaned:
        return ""

    if cleaned in _INVALID_TOKENS:
        return ""

    if cleaned.isdigit() and len(cleaned) < 7:
        return ""

    digits = re.sub(r"\D", "", cleaned)
    if not digits:
        return ""

    # Reject if digits start with 8 (invalid passport/IIN)
    if digits.startswith("8"):
        return ""

    return cleaned

