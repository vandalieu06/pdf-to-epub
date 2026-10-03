---
code: "17"
title: "Report pages ignored by pdf2docx"
status: completed
version: "0.1.0"
project: "pdf-to-epub"
date: 2026-09-18
tags: [spec, sdd]
affected_files:
  - src/pdf_to_epub/core/docx/convert.py
  - src/pdf_to_epub/core/pipeline.py
  - src/pdf_to_epub/core/models.py
  - src/pdf_to_epub/cli.py
  - tests/core/docx/test_convert.py
---

# 17 — Report pages ignored by pdf2docx

## Purpose

Tell the user when `pdf2docx` skips a page, so missing content is not silent.

## Context

`pdf2docx` logged `ERROR:root:Ignore page 4 due to parsing page error: list index out of
range` for a full-page landscape illustration page, and the page was silently lost.

## Proposed change

- `core/docx/convert.py` captures pdf2docx's log output while converting and extracts the page
  numbers from `Ignore page <n>` messages; `to_docx` returns a `DocxConversion` result with
  `path` and `ignored_pages`.
- `ConversionReport.ignored_pages` carries them to the CLI.
- The CLI prints a warning (e.g. `warning: pdf2docx ignored pages 4`) when non-empty.

Inserting the missing page's image back is out of scope (future work); this change only makes
the loss visible.

## Technical decision

- Capture via a temporary `logging.Handler` attached to the root logger (pdf2docx logs at
  root), removed after the conversion; no dependency on pdf2docx internals.
- Only the reporting is added; conversion behaviour is unchanged.

## Affected files

- `src/pdf_to_epub/core/docx/convert.py`, `core/pipeline.py`, `core/models.py`, `core/cli.py`.
- `tests/core/docx/test_convert.py`.

## Tests

- A log record `Ignore page 4 …` is parsed into `ignored_pages == [4]`.
- The CLI prints the warning when the report has ignored pages.

## Acceptance criteria

- Ignored pages are surfaced in the report and the CLI.
- `pytest -q` and `ruff check .` pass.
