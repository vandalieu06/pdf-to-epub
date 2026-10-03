"""PDF -> DOCX conversion, wrapping `pdf2docx` behind a stable interface."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_IGNORED_PAGE_RE = re.compile(r"Ignore page (\d+)")


class DocxConversionError(RuntimeError):
    """Raised when the PDF -> DOCX conversion fails."""


@dataclass(slots=True)
class DocxConversion:
    """Result of a PDF -> DOCX conversion."""

    path: Path
    ignored_pages: list[int] = field(default_factory=list)


class _IgnoredPageHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.pages: list[int] = []

    def emit(self, record: logging.LogRecord) -> None:
        match = _IGNORED_PAGE_RE.search(record.getMessage())
        if match:
            self.pages.append(int(match.group(1)))


def to_docx(
    pdf_path: Path,
    docx_path: Path,
    *,
    progress: Callable[[str], None] | None = None,
) -> DocxConversion:
    """Convert a PDF to DOCX using pdf2docx.

    `pdf2docx` is frozen upstream, so it is isolated in this module and can be
    replaced without touching the rest of the pipeline. Pages that pdf2docx skips are
    reported back instead of being lost silently.
    """
    if progress:
        progress("Converting PDF to DOCX")
    try:
        from pdf2docx import Converter
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise DocxConversionError(f"pdf2docx is not available: {exc}") from exc

    docx_path.parent.mkdir(parents=True, exist_ok=True)
    handler = _IgnoredPageHandler()
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    converter = Converter(str(pdf_path))
    try:
        converter.convert(str(docx_path))
    except Exception as exc:  # noqa: BLE001 - re-raised as a domain error
        raise DocxConversionError(f"failed to convert {pdf_path} to DOCX: {exc}") from exc
    finally:
        converter.close()
        root_logger.removeHandler(handler)

    if not docx_path.exists():
        raise DocxConversionError(f"pdf2docx produced no output at {docx_path}")
    return DocxConversion(path=docx_path, ignored_pages=sorted(set(handler.pages)))
