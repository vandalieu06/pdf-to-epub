---
code: "10"
title: "Paragraph reflow (split dialogue, merge page-break continuations)"
status: completed
version: "0.1.0"
project: "pdf-to-epub"
date: 2026-09-18
tags: [spec, sdd]
affected_files:
  - src/pdf_to_epub/core/docx/reflow.py
  - src/pdf_to_epub/core/docx/clean.py
  - src/pdf_to_epub/core/models.py
  - src/pdf_to_epub/core/config.py
  - src/pdf_to_epub/core/pipeline.py
  - src/pdf_to_epub/cli.py
  - tests/core/docx/test_reflow.py
  - docs/uso.md
  - docs/arquitectura.md
  - docs/features.md
---

# 10 — Paragraph reflow (split dialogue, merge page-break continuations)

## Purpose

Fix the two paragraph artifacts `pdf2docx` introduces so dialogue speakers are separated
and sentences broken across pages are rejoined.

## Context

`pdf2docx` reconstructs text from positioned glyphs, which produces two opposite errors in
the intermediate DOCX (and therefore in the EPUB):

1. **Logical paragraph split across pages/newspapers** becomes several paragraphs, e.g.
   `"…cuyo rostro"` / `"atractivo podría hacerlo irresistible…"`. Measured in the
   validation novel: **102** such continuations.
2. **Several logical paragraphs (dialogue lines) crammed into one paragraph** separated by
   `<w:br/>`. Measured: **424** paragraphs contain internal breaks (**707** breaks total).
   In HTML the breaks collapse to spaces, so different speakers run together.

The user confirmed the intended rule: a break is a paragraph boundary when the text before
it ends a sentence or the text after starts with a quote/dash; otherwise it is a line wrap
(space). And a paragraph that continues the previous one (previous does not end a sentence,
next starts lowercase) should be joined.

## Proposed change

New pass `core/docx/reflow.py`, applied by `clean_document` (default on, `--no-reflow` to
disable), before chapter splitting:

- `reflow_document(document) -> ReflowReport`.
- **Split**: for each body paragraph, replace `<w:br/>`/`<w:cr/>` with a paragraph boundary
  when `left.rstrip()` ends in `. ! ? … : ; " » )` **or** `right.lstrip()` starts with
  `" ' “ ‘ « - —`; otherwise replace the break with a single space. Formatting is preserved
  by cloning the run properties into the resulting runs and copying the paragraph's
  `w:pPr`.
- **Merge**: when a paragraph's text does not end a sentence and the next starts with a
  lowercase letter (and neither starts with a quote/dash), move the next paragraph's inline
  content into the previous one with a separating space and remove the now-empty paragraph.
- **Skip** headings (`Heading *`, `Title`), empty paragraphs and paragraphs containing a
  `w:drawing`/`w:pict` (so text is never merged across an illustration).
- Counts reported: `split_paragraphs`, `merged_paragraphs`.

## Technical decision

- Applied at the **DOCX** stage so the editable intermediate and the EPUB stay consistent.
- Rules are purely textual and conservative; ambiguous cases remain for manual review, as
  the user expects.
- Runs and paragraph properties are preserved so italics/bold and indentation survive.
- A single space (not a paragraph break) is used for line wraps, which is also what HTML
  rendering did implicitly for `\n`.
- The pass is idempotent enough to run after table repair and before splitting.

## Affected files

- `src/pdf_to_epub/core/docx/reflow.py` — new.
- `src/pdf_to_epub/core/docx/clean.py` — call the reflow pass.
- `src/pdf_to_epub/core/models.py` — `ReflowReport`, counters on `DocxCleanReport` and
  `ConversionReport`.
- `src/pdf_to_epub/core/config.py` — `reflow_paragraphs`.
- `src/pdf_to_epub/core/pipeline.py`, `src/pdf_to_epub/cli.py` — wiring and `--no-reflow`.
- `tests/core/docx/test_reflow.py` — new.
- `docs/uso.md`, `docs/arquitectura.md`, `docs/features.md`.

## Tests

- A paragraph with a dialogue break (`"¿Qué pasa?" <br/> "Nada", dijo.`) becomes two
  paragraphs.
- A paragraph with a mid-sentence break (`"…mientras se <br/> pellizcaba…"`) becomes one
  paragraph with a space.
- Two continuation paragraphs (`"cuyo rostro"`, `"atractivo…"`) are merged; a paragraph
  ending in `.` is not merged.
- An image paragraph between two text paragraphs prevents merging.
- Headings and empty paragraphs are left untouched.
- `--no-reflow` leaves paragraphs unchanged.

## Acceptance criteria

- Dialogue lines that were joined by `<w:br/>` end up as separate paragraphs.
- Page-break continuations are rejoined.
- Images, headings and formatting are preserved.
- `pytest -q` and `ruff check .` pass.
