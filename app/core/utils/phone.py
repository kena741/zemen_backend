"""Phone number utilities for Ethiopian phone formats and query variants."""

from __future__ import annotations

import re


def normalize_ethiopian_phone(phone: str) -> str:
    """Normalize Ethiopian phone numbers to international +251 standard.

    Accepted formats:
        - +251911223344 -> +251911223344
        - 251911223344  -> +251911223344
        - 0911223344   -> +251911223344
        - 911223344    -> +251911223344
        - 0711223344   -> +251711223344 (Safaricom Ethiopia 07...)
        - +251711223344 -> +251711223344
    """
    clean = re.sub(r"[\s\-\(\)]+", "", phone.strip())

    if clean.startswith("+251"):
        digits = clean[4:]
        if len(digits) == 9 and digits[0] in ("9", "7"):
            return f"+251{digits}"
        return clean

    if clean.startswith("251"):
        digits = clean[3:]
        if len(digits) == 9 and digits[0] in ("9", "7"):
            return f"+251{digits}"
        return f"+{clean}"

    if clean.startswith("0") and len(clean) == 10 and clean[1] in ("9", "7"):
        return f"+251{clean[1:]}"

    if len(clean) == 9 and clean[0] in ("9", "7"):
        return f"+251{clean}"

    # Return bare string if unrecognized format (fallback)
    return clean


def get_phone_search_variants(phone: str) -> list[str]:
    """Generate all common representations of an Ethiopian phone number.

    Used in SQL ILIKE / IN / OR queries so that legacy records stored with or
    without the country prefix still resolve correctly.
    """
    clean = re.sub(r"[\s\-\(\)]+", "", phone.strip())
    # Extract the 9 local digits if possible
    digits_9 = None

    if clean.startswith("+251") and len(clean) >= 13:
        digits_9 = clean[4:13]
    elif clean.startswith("251") and len(clean) >= 12:
        digits_9 = clean[3:12]
    elif clean.startswith("0") and len(clean) >= 10:
        digits_9 = clean[1:10]
    elif len(clean) == 9:
        digits_9 = clean

    if digits_9 and len(digits_9) == 9 and digits_9[0] in ("9", "7"):
        return [
            f"+251{digits_9}",
            f"251{digits_9}",
            f"0{digits_9}",
            digits_9,
        ]

    return [clean]

