---
code: "02"
title: "Header/footer detection and removal"
status: completed
version: "0.1.0"
project: "pdf-to-epub"
date: 2026-09-18
tags: [spec, sdd]
affected_files:
  - src/pdf_to_epub/core/pdf/headers_footers.py
  - src/pdf_to_epub/core/docx/clean.py
  - src/pdf_to_epub/core/models.py
  - src/pdf_to_epub/core/config.py
  - tests/core/pdf/test_headers_footers.py
  - tests/core/docx/test_clean.py
  - docs/arquitectura.md
---

# 02 — Header/footer detection and removal

## Purpose

Remove repeated page headers and footers (and page numbers) from the source PDF before it
is converted to DOCX, and guarantee they do not survive in the intermediate DOCX.

## Context

A PDF has no semantic notion of header/footer: they are ordinary text positioned in the
top/bottom bands of each page. They can nevertheless be detected because they tend to
**repeat across pages** at a **similar vertical position** and **use smaller/different
fonts** than the body. Detection is therefore heuristic; a robust default plus manual
editing of the resulting EPUB is the accepted strategy.

Removing them at the PDF stage is preferred over post-DOCX removal because page geometry
is available there and `pdf2docx` reflows content, losing the page-band information. A
secondary DOCX pass handles leftovers regardless.

## Proposed change

### Stage 2a — PDF detection and redaction (`core/pdf/headers_footers.py`)

1. Compute page geometry and margin bands as a fraction of page height
   (default: top 8%, bottom 8%; configurable).
2. Collect text blocks (`page.get_text("blocks")`) whose bounding box lies (mostly) within
   a band, for every page.
3. Normalize block text (strip, collapse whitespace, drop digits used as page numbers) and
   count occurrences across pages. A normalized string appearing on **≥ `min_ratio` of
   pages** (default 0.5, and at least 2 pages) is a **candidate**.
4. Also flag blocks that look like bare page numbers in a band (regex `^[\divxlcdmIVXLCDM.\-–— ]+$`).
5. Apply redaction annotations over candidate rectangles and remove them via
   `page.apply_redactions()` (removes the glyphs, and images only if configured).
6. Write `<input-stem>.clean.pdf` and return its path together with a
   `HeaderFooterReport` (candidates found, pages affected).

Guardrails:

- Never redact within the central band (between the top and bottom bands).
- If a candidate covers more than `max_band_ratio` of a page's text area, skip it (avoid
  deleting real content on pages with little text).
- If no candidates are found, return the original path unchanged (no copy).
- Detection results are logged so the user can inspect/adjust thresholds.

### Stage 4a — DOCX safety net (`core/docx/clean.py`)

- Clear the content of `section.header` and `section.footer` for every section
  (empty their paragraphs and remove tables/other children).
- Remove boundary paragraphs whose text repeats across the document (same normalization
  as above) and that match the page-number regex, only when they sit at the start/end of a
  page-influenced block. This is best-effort; it must never delete paragraphs in the middle
  of the body.
- Any removal is recorded in the `ConversionReport` for transparency.

### Options (see spec 05 / `config.py`)

- `--no-clean` disables both passes.
- `--header-margin` / `--footer-margin` accept fractions or `auto` (default `auto`).
- `--max-removals`/report is informational only.

## Technical decision

- Use PyMuPDF **redaction** (not just extraction-time clipping) so the removed text is
  physically gone and cannot leak into `pdf2docx`.
- Work at the **block** level, not word/line level, to avoid partially cutting a paragraph
  that legitimately reaches a band.
- Heuristic normalized-text counting is preferred over DBSCAN/clustering for v0.1.0
  (simpler, deterministic, testable); clustering is a documented future option.
- All thresholds are configurable and have conservative defaults so failures degrade to
  "a header remains" rather than "body text was deleted".

## Affected files

- `src/pdf_to_epub/core/pdf/headers_footers.py` — new.
- `src/pdf_to_epub/core/docx/clean.py` — DOCX header/footer clearing + repeated-line pass.
- `src/pdf_to_epub/core/models.py` — `HeaderFooterReport`.
- `src/pdf_to_epub/core/config.py` — margin/threshold options.
- `tests/core/pdf/test_headers_footers.py`, `tests/core/docx/test_clean.py` — new.
- `docs/arquitectura.md` — document the heuristic and its limits.

## Tests

- Build a synthetic PDF with PyMuPDF: N pages, a body paragraph on each, a constant header
  line and a page-number footer. Assert the cleaned PDF, re-extracted, contains the body on
  every page and **no** header/footer text.
- Mutated fixture where the header changes text on one page: assert the changed page's
  header is not counted as a candidate (below `min_ratio`) and, by default, is not removed.
- PDF with no headers/footers: assert `clean_pdf` returns the original path and no
  redaction is applied.
- DOCX fixture with a header and footer in `section.header/footer`: assert they become
  empty after `clean_document`.
- Guardrail test: a centered, legitimate paragraph that touches the band must not be
  removed.

## Acceptance criteria

- Repeated headers/footers and page numbers are absent from the `.clean.pdf` and from the
  generated EPUB for the standard fixture.
- Body text on every page survives.
- With no candidates, the original PDF is used untouched.
- Thresholds are configurable via CLI options and covered by tests.
