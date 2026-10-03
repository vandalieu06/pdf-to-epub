from __future__ import annotations

import logging

from pdf_to_epub.core.docx.convert import _IgnoredPageHandler


def _record(message: str) -> logging.LogRecord:
    return logging.LogRecord("root", logging.ERROR, __file__, 1, message, None, None)


def test_ignored_page_handler_parses_page() -> None:
    handler = _IgnoredPageHandler()
    handler.emit(
        _record("Ignore page 4 due to parsing page error: list index out of range")
    )
    assert handler.pages == [4]


def test_ignored_page_handler_ignores_other_messages() -> None:
    handler = _IgnoredPageHandler()
    handler.emit(_record("Starting to convert"))
    assert handler.pages == []
