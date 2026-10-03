---
code: "06"
title: "False-positive table repair"
status: completed
version: "0.1.0"
project: "pdf-to-epub"
date: 2026-09-18
tags: [spec, sdd]
affected_files:
  - src/pdf_to_epub/core/docx/clean.py
  - src/pdf_to_epub/core/models.py
  - src/pdf_to_epub/core/config.py
  - src/pdf_to_epub/core/pipeline.py
  - src/pdf_to_epub/cli.py
  - tests/core/docx/test_clean.py
  - tests/core/test_pipeline.py
  - docs/arquitectura.md
  - docs/uso.md
  - docs/features.md
---

# 06 — False-positive table repair

## Purpose

Undo `pdf2docx`'s false-positive table detection: certain justified text lines are
reconstructed as one-row tables with one word per cell, which pollutes the DOCX and makes
the EPUB text copy as one word per line.

## Context

`pdf2docx` analyzes each page independently and, on some lines with wide inter-word gaps
(justified text, typically the first line of a page), interprets the gaps as column
separators. The result is a table with **exactly one row** and one cell per word, e.g.:

```html
<table>
  <tr>
    <td>avergonzado</td><td>por</td><td>eso.</td>
    <td>Los</td><td>cambios</td> ... <td>eran</td>
  </tr>
</table>
```

The original PDF contains no table; this is converter noise. In the real novel used for
validation, all 7 tables in the EPUB had this shape (1 row × 9–10 columns).

A real light-novel table has several rows and columns, so a one-row table is, in practice,
a mis-segmented line of prose. Repairing it in the intermediate DOCX is preferred because
the DOCX is the manual intervention point, so both the DOCX and the resulting EPUB are
clean.

## Proposed change

Add a table-repair pass to `core/docx/clean.py`:

- Iterate `document.tables`.
- A table is a **word-grid false positive** when `len(rows) == 1` and it has at least
  `MIN_COLUMNS = 3` non-empty cells.
- For each false positive: join the non-empty cell texts with a single space, insert a new
  `w:p` immediately **before** the table element, then remove the table element.
- Real tables (two or more rows) are left untouched.
- Report the number of repaired tables in `DocxCleanReport.repaired_tables` and
  `ConversionReport.repaired_tables`.

New option `keep_tables: bool = False` (CLI `--keep-tables`) disables the repair, keeping
`pdf2docx`'s output as-is.

## Technical decision

- Repair happens in the **DOCX** (not only at EPUB render time) so the editable
  intermediate presented to the user is also clean.
- The heuristic is deliberately conservative: only **single-row** tables are repaired.
  Deleting a genuine one-row table would be worse than leaving a stray table, and the user
  can always re-enable tables with `--keep-tables`.
- Joined text preserves reading order (cells are already in left-to-right order) but not
  formatting marks inside cells; cells contain plain text in the false-positive cases.
- The inserted paragraph is plain `Normal`; later paragraph reflow (spec 07) can merge it
  with the preceding split paragraph.

## Affected files

- `src/pdf_to_epub/core/docx/clean.py` — repair pass.
- `src/pdf_to_epub/core/models.py` — `DocxCleanReport.repaired_tables`,
  `ConversionReport.repaired_tables`.
- `src/pdf_to_epub/core/config.py` — `keep_tables`.
- `src/pdf_to_epub/core/pipeline.py` — pass the option and record the count.
- `src/pdf_to_epub/cli.py` — `--keep-tables` flag and summary line.
- `tests/core/docx/test_clean.py` — repair and preservation tests.
- `tests/core/test_pipeline.py` — end-to-end assertion of no false tables.
- `docs/arquitectura.md`, `docs/uso.md`, `docs/features.md` — document the behavior.

## Tests

- DOCX with a one-row, ten-column table of words: after `clean_document`, the table is
  gone, a paragraph with the joined sentence exists in the same position, and
  `repaired_tables == 1`.
- DOCX with a real 3×2 table: it is preserved (still a table) and `repaired_tables == 0`.
- DOCX with a one-row table of fewer than 3 non-empty cells: preserved.
- `keep_tables=True`: the one-row table is preserved and `repaired_tables == 0`.
- EPUB of a fixture containing a word-grid table contains no `<table>`; the words appear
  as a single `<p>`.

## Acceptance criteria

- No `<table>` in the EPUB for the validation novel that originated from this false
  positive; real tables remain.
- `--keep-tables` disables the repair.
- `repaired_tables` is reported in the CLI summary.
- `pytest -q` and `ruff check .` pass.
