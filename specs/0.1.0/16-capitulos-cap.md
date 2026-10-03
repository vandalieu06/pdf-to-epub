---
code: "16"
title: 'Recognize "CAP N" chapter markers'
status: completed
version: "0.1.0"
project: "pdf-to-epub"
date: 2026-09-18
tags: [spec, sdd]
affected_files:
  - src/pdf_to_epub/core/epub/split.py
  - tests/core/epub/test_split.py
---

# 16 — Recognize "CAP N" chapter markers

## Purpose

Detect chapters in books that use abbreviated markers such as `CAP 1:`, `CAP. 2`, `CAP 3`,
in addition to `Capítulo 1` / `Chapter 1`.

## Context

`Kanojo ga Harem o Susumete Kuru. 3` marks chapters as `CAP 1: LA VISITA DOMICILIARIA DE
AOI`, `CAP 2: …`, etc. The chapter regex only matched `chapter`/`capítulo`, so the whole book
ended up as **1 chapter**. The table of contents on page 3 uses `Capítulo 1..6` and must stay
excluded (it is long and/or has dot leaders).

## Proposed change

In `core/epub/split.py`, add `cap` to `_CHAPTER_RE` as a word (`\b`), so it matches `CAP 1`,
`CAP. 1`, `CAP:`. The existing guards (max title length, no trailing sentence punctuation, no
dot leaders, leading quotes stripped) remain.

## Technical decision

- `cap` with a trailing word boundary does not match `capital`/`capaz`; the following digit or
  punctuation makes the intent explicit.
- Case-insensitive matching already covers the uppercase form.

## Affected files

- `src/pdf_to_epub/core/epub/split.py`.
- `tests/core/epub/test_split.py`.

## Tests

- `CAP 1: ...`, `CAP. 2 ...` and `cap 3` start chapters.
- `capital de provincia` or a long TOC paragraph does not.

## Acceptance criteria

- Validation novel produces ~7 chapters (front matter + CAP 1..6).
- `pytest -q` and `ruff check .` pass.
