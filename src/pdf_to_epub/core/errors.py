"""Domain exceptions mapped to CLI exit codes by the presentation layer."""

from __future__ import annotations


class PipelineError(RuntimeError):
    """Base class for pipeline failures."""


class ValidationError(PipelineError):
    """Invalid usage or input (exit code 1)."""


class PdfStageError(PipelineError):
    """Failure while reading or cleaning the PDF (exit code 2)."""


class DocxStageError(PipelineError):
    """Failure while producing or cleaning the DOCX (exit code 3)."""


class EpubStageError(PipelineError):
    """Failure while building the EPUB (exit code 4)."""
