---
code: "19"
title: "Split adjacent dialogues within a paragraph"
status: completed
version: "0.1.0"
project: "pdf-to-epub"
date: 2026-09-20
tags: [spec, sdd]
affected_files:
  - src/pdf_to_epub/core/docx/reflow.py
  - tests/core/docx/test_reflow.py
  - docs/arquitectura.md
  - docs/features.md
---

# 19 — Split adjacent dialogues within a paragraph

## Purpose

Separate two quoted dialogues that pdf2docx packed into one paragraph with only a space
between them, so each speaker starts on its own line.

## Context

```
“Ah, sí dijeron que el antiguo dueño de esta mansión pasó toda su vida solo.” “¿Así que se
convirtió en un fantasma porque lamentaba no ser popular?” Lenka y Tea hablaron...
```

The paragraph has no `w:br`, so the reflow pass (spec 10) left it joined. The pattern
`closing quote + spaces + opening quote` is common: measured in the library, e.g. Kanojo 101,
Koroshiya 59, Poison volumes 26–49 occurrences. In the validation volume all 49 matches had
sentence punctuation before the closing quote (no false positives).

## Proposed change

Add a forced-boundary rule to `core/docx/reflow.py`, applied after the `w:br` split pass and
before the merge pass:

- Pattern: a closing quote `["”»'’]` followed by 1–3 spaces followed by an opening quote
  `["“«'‘]` (both straight and curly quotes).
- The boundary is a paragraph break (the intervening spaces are dropped); it does **not**
  depend on punctuation or on `w:br`.
- Detected both inside a run's text and at a run junction (the usual case, where the closing
  quote ends one run and the opening quote starts the next); run properties (`w:rPr`) are
  cloned so italics/bold survive.
- Counted in `split_paragraphs`; `--no-reflow` disables it.
- Not applied to lists with a comma (`", "`) or dashes (`" — "`), which do not match.

## Technical decision

- Implemented in the DOCX so the optional intermediate (`--keep-intermediate`) is also
  correct, consistent with the rest of the reflow rules.
- The rule is textual (no reliance on line breaks), complementing the `w:br` rule.

## Affected files

- `src/pdf_to_epub/core/docx/reflow.py`
- `tests/core/docx/test_reflow.py`
- `docs/arquitectura.md`, `docs/features.md`

## Tests

- `“A.” “B?” narrativa` → two paragraphs (`“A.”` and `“B?” narrativa`).
- Straight quotes `"A." "B"` and single quotes `’A’ ‘B’` also split.
- No split for `“A”, “B” y “C”` (comma) or `“A” — “B”` (dash).
- Italic runs are preserved after the split.

## Acceptance criteria

- Adjacent dialogues are separate paragraphs in the DOCX and the EPUB.
- No false splits on lists/dashes; `split_paragraphs` reports the cuts.
- `pytest -q` and `ruff check .` pass.
