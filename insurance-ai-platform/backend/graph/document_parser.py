"""Deterministic field extraction from claim document text.

This is the text intake step: given already-decoded text, pull out the
structured fields extraction_node needs via labeled-line pattern
matching -- no OCR, no vision models, no LLM call here. That text may
have come from a PDF's embedded text layer, a plain-text claim form, or
Tesseract OCR run on an image/scanned-PDF upload (see
app.services.storage_service.extract_text) -- this module doesn't care
which; by the time text reaches it, decoding is someone else's job.

The parser only ever supplements -- extraction_node treats any field
already present in raw_input as authoritative and never lets a parsed
value override an explicitly provided one.
"""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from .rules import KNOWN_CLAIM_TYPES

# Each field maps to the label synonyms a real invoice/claim form tends to
# use, matched at the start of a line up to a colon, case-insensitively.
_FIELD_LABELS: dict[str, tuple[str, ...]] = {
    "claim_type": ("claim type",),
    "date_of_service": ("date of service", "service date", "dos"),
    "billed_amount": ("billed amount", "total billed", "amount due", "total charge", "total"),
    "procedure_codes": ("procedure codes", "procedure code", "cpt codes", "cpt code", "procedure"),
    "diagnosis_codes": ("diagnosis codes", "diagnosis code", "icd codes", "icd code", "diagnosis"),
}

_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y")


def _parse_date(value: str) -> str | None:
    value = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_amount(value: str) -> str | None:
    cleaned = value.strip().lstrip("$").replace(",", "")
    try:
        return str(Decimal(cleaned).quantize(Decimal("0.01")))
    except InvalidOperation:
        return None


def _parse_code_list(value: str) -> list[str]:
    parts = re.split(r"[,/;]|\s{2,}|\s+and\s+", value.strip(), flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


def _parse_claim_type(value: str) -> str | None:
    # Only ever produces one of the recognized categories or nothing --
    # never a messy free-text value that would trip the "unrecognized
    # claim type" rule and auto-deny a claim purely because of a parsing
    # quirk.
    normalized = value.strip().lower()
    return normalized if normalized in KNOWN_CLAIM_TYPES else None


_PARSERS = {
    "date_of_service": _parse_date,
    "billed_amount": _parse_amount,
    "procedure_codes": _parse_code_list,
    "diagnosis_codes": _parse_code_list,
    "claim_type": _parse_claim_type,
}


def extract_fields_from_text(text: str) -> dict[str, Any]:
    """Returns whatever fields it could confidently find. Fields it
    doesn't find (or can't parse cleanly) are simply absent from the
    result -- callers merge this under explicit data, never over it.
    """
    fields: dict[str, Any] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if ":" not in line:
            continue
        label, _, value = line.partition(":")
        label = label.strip().lower()
        value = value.strip()
        if not value:
            continue

        for field_name, synonyms in _FIELD_LABELS.items():
            if field_name in fields:
                continue  # first match wins if a form repeats a label
            if label in synonyms:
                parsed = _PARSERS[field_name](value)
                if parsed:
                    fields[field_name] = parsed
                break

    return fields
