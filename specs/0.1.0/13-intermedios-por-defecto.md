---
code: "13"
title: "Remove intermediate files by default"
status: completed
version: "0.1.0"
project: "pdf-to-epub"
date: 2026-09-18
tags: [spec, sdd]
affected_files:
  - src/pdf_to_epub/core/config.py
  - src/pdf_to_epub/cli.py
  - tests/core/test_pipeline.py
  - tests/test_cli.py
  - docs/uso.md
  - README.md
  - docs/features.md
  - specs/0.1.0/00-changelog.md
  - specs/0.1.0/05-cli.md
---

# 13 — Remove intermediate files by default

## Purpose

Make `pdf-to-epub` tidy by default: after a successful run only the EPUB remains. Keeping
the intermediate `.clean.pdf` and `.docx` becomes an explicit choice
(`--keep-intermediate`), which is more functional for everyday use.

## Context

Since v0.1.0 the pipeline kept `*.clean.pdf` and `*.docx` next to the output (or in
`--workdir`), because the DOCX is the manual-correction artifact. In practice the common
run only wants the EPUB; the intermediates are only needed when the automatic cleaning has
to be reviewed or edited. The trade-off was decided in spec 05; it is now inverted.

## Proposed change

- `core/config.py`: `keep_intermediate: bool = False`.
- `core/cli.py`: `typer.Option(False, "--keep-intermediate/--clean-intermediate", ...)`.
  Both flags remain: `--keep-intermediate` keeps the files, `--clean-intermediate` stays as
  a valid (now redundant) explicit alias, so existing scripts keep working.
- `core/pipeline.py` is unchanged: on success it removes the `.clean.pdf` (only when it was
  created) and the `.docx`; on failure it leaves them for debugging.
- CLI summary: when keeping, print the paths of the kept intermediates; otherwise print a
  short note that they were removed and how to keep them.
- `--workdir` only changes where the intermediates are created; the default still removes
  them unless `--keep-intermediate` is passed.

## Technical decision

- Inverting the default at the configuration/CLI layer keeps the pipeline logic untouched
  and the change small and testable.
- Keeping `--clean-intermediate` avoids breaking existing invocations.
- Cleanup still happens only after a successful conversion, so failures remain debuggable.

## Affected files

- `src/pdf_to_epub/core/config.py`, `core/cli.py`.
- `tests/core/test_pipeline.py`, `tests/test_cli.py`.
- `docs/uso.md`, `README.md`, `docs/features.md`.
- `specs/0.1.0/00-changelog.md`; note in `specs/0.1.0/05-cli.md`.

## Tests

- Default run: the EPUB exists and neither `.clean.pdf` nor `.docx` remain.
- `--keep-intermediate`: both intermediates exist after a successful run.
- CLI plumbing: default maps to `keep_intermediate=False`; `--keep-intermediate` maps to
  `True` and `--clean-intermediate` to `False`.
- A failed run leaves the intermediates in place.

## Acceptance criteria

- `pdf-to-epub convert novela.pdf` leaves only `novela.epub`.
- `pdf-to-epub convert novela.pdf --keep-intermediate` keeps `.clean.pdf` and `.docx`.
- `pytest -q` and `ruff check .` pass.
