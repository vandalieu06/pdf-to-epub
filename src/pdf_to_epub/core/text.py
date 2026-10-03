"""Shared text helpers used by the PDF and DOCX stages."""

from __future__ import annotations

import re

_PAGE_NUMBER_RE = re.compile(
    r"^[\s\-–—.()\[\]]*[0-9ivxlcdm]{1,8}[\s\-–—.()\[\]]*$",
    re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    """Collapse whitespace so slightly different blocks compare equal."""
    return " ".join(text.split()).strip()


def is_page_number(text: str) -> bool:
    """Return True for strings that look like a bare page number."""
    return bool(_PAGE_NUMBER_RE.match(text.strip()))
