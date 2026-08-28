from __future__ import annotations

import re


_INVALID_TOKENS = {"DOCUMENT", "DOCUMENTNUMBER", "PASSPORT", "IIN", "ИИН"}


def _strip_excel_float_tail(value: str) -> str:
    """Excel/pandas отдают номер паспорта как float ("14639484.0"), когда в
    колонке есть пустые ячейки. Без этого хвост ".0" превращался в лишний
    ноль в конце номера ("146394840")."""
    text = str(value or "").strip()
    match = re.fullmatch(r"([A-ZА-Я]*\d+)\.0+", text.upper())
    if match:
        return match.group(1)
    return text


def normalize_document(value: str) -> str:
    cleaned = re.sub(r"[^\w]", "", _strip_excel_float_tail(value).upper().strip())
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

