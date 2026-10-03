---
code: "05"
title: "CLI interface"
status: completed
version: "0.1.0"
project: "pdf-to-epub"
date: 2026-09-18
tags: [spec, sdd]
affected_files:
  - src/pdf_to_epub/cli.py
  - src/pdf_to_epub/core/config.py
  - pyproject.toml
  - tests/test_cli.py
  - docs/uso.md
  - README.md
---

# 05 — CLI interface

> **Superseded (partially) by [spec 13](13-intermedios-por-defecto.md):** the default for
> intermediates is now to remove them; `--keep-intermediate` keeps them.

## Purpose

Define the `pdf-to-epub` command-line interface: commands, options, intermediate-artifact
handling, exit codes, and progress/error output.

## Context

The tool is a single-purpose converter invoked as `pdf-to-epub convert <input.pdf>`. It
must be usable interactively (clear progress via `rich`) and in scripts (deterministic exit
codes, no interactive prompts). The pipeline produces intermediate files
(`*.clean.pdf`, `*.docx`) that the user may want to inspect; by default the DOCX should be
kept only if requested.

## Proposed change

Use **Typer** with a `rich` console. Entry point
`pdf-to-epub = "pdf_to_epub.cli:app"` (calling `app` from `pdf_to_epub.cli`).

### `convert` command

```
pdf-to-epub convert INPUT.pdf [OPTIONS]
```

Core options:

| Option | Default | Description |
|--------|---------|-------------|
| `-o, --output PATH` | `INPUT.epub` | Output EPUB path. |
| `--keep-intermediate` / `--no-keep-intermediate` | keep | Keep `.clean.pdf`/`.docx`; `--clean-intermediate` removes them on success. |
| `--workdir PATH` | alongside input | Directory for intermediate files. |
| `--no-clean` | off | Disable header/footer removal (both passes). |
| `--header-margin FLOAT\|auto` | `auto` | Top band as fraction of page height. |
| `--footer-margin FLOAT\|auto` | `auto` | Bottom band as fraction of page height. |
| `--min-header-ratio FLOAT` | `0.5` | Fraction of pages a repeated line must appear on. |
| `--title TEXT` | — | Override EPUB title. |
| `--author TEXT` | — | Override EPUB author. |
| `--language TEXT` | `es` fallback | Override/ set EPUB language. |
| `--identifier TEXT` | uuid4 | Override EPUB identifier. |
| `--cover PATH` | auto | Use image file as cover. |
| `--keep-all-images` | off | Do not filter small/decorative images. |
| `--min-image-px INT` | `24` | Minimum image side to keep. |
| `--quiet` / `-q` | off | Suppress progress; only errors. |
| `--verbose` / `-v` | off | Debug logging. |

Behavioral rules:

- If `-o` is omitted, output is `INPUT` with the `.epub` suffix, in the input directory.
- Refuse to overwrite an existing output unless `--force` (default: no overwrite).
- Fail fast if the input is not a readable PDF (only PDFs are accepted in v0.1.0).
- Atomic output: write to a temp file and `os.replace` on success.
- Intermediates go to `--workdir` (default: input directory) with names derived from the
  input stem; removed on success only when `--clean-intermediate` is set (default keeps the
  DOCX to allow manual correction, matching the project's workflow).

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success. |
| `1` | Validation error from the pipeline (unreadable/non-PDF input, output exists without `--force`, bad numeric option). |
| `2` | Usage error raised by the CLI framework (missing/invalid arguments, unknown option). |
| `3` | PDF stage error (parse, encrypted/unsupported, redaction failure). |
| `4` | DOCX stage error (`pdf2docx` failure, DOCX cleanup failure). |
| `5` | EPUB stage error (build/validation failure). |
| `6` | I/O error (permission denied, disk full). |

`2` is reserved for the CLI framework (Typer/Click) and is therefore not emitted by the
pipeline itself; `core` exceptions map to `1`, `3`, `4`, `5`. `core` never calls
`sys.exit`.

### Progress and logging

- `rich` progress with one phase per stage (inspect, clean PDF, to DOCX, clean DOCX,
  build EPUB), plus a final summary (title, chapters, images, time).
- `--verbose` emits stage diagnostics (candidates found, images dropped) as structured
  logs.
- `--quiet` prints nothing except on error.

### Output summary

On success, print the output path and a one-line report: pages, header/footer removals,
images embedded, chapters. Machine-readable output (`--json`) is out of scope for v0.1.0
and documented as a future option.

## Technical decision

- **Typer** for argument parsing and **rich** for presentation, consistent with the
  project's other tooling; `core` stays free of CLI/framework imports (dependencies
  injected, progress via callbacks if needed).
- Explicit, documented exit codes so the tool is scriptable.
- Keep intermediates by default because manual DOCX/EPUB correction is part of the intended
  workflow; provide `--clean-intermediate` for tidy runs.
- `--force` gating prevents accidental data loss.

## Affected files

- `src/pdf_to_epub/cli.py` — new Typer app and entrypoint.
- `src/pdf_to_epub/core/config.py` — `ConversionOptions` populated from CLI flags.
- `pyproject.toml` — `[project.scripts] pdf-to-epub = "pdf_to_epub.cli:app"`.
- `tests/test_cli.py` — new (Typer `CliRunner`).
- `docs/uso.md` — full option reference and examples.
- `README.md` — short quickstart.

## Tests

- `CliRunner` tests with synthetic fixtures: `convert` writes the EPUB and exits `0`.
- Existing output without `--force` exits `1` and does not modify the file.
- Missing/non-PDF input exits `1`.
- Encrypted/corrupt PDF exits `3`; mocked `pdf2docx` failure exits `4`; mocked EPUB build
  failure exits `5`.
- `--quiet` produces no stdout on success; `--verbose` includes stage diagnostics.
- `--clean-intermediate` removes intermediates; default keeps them.
- `--title/--author/--language/--cover` overrides reach the EPUB metadata/cover.

## Acceptance criteria

- Documented options and exit codes behave as specified and are covered by tests.
- Intermediates are kept by default and removed only with `--clean-intermediate`.
- Output is never overwritten without `--force`.
- `core` remains free of `typer`/`rich` imports (enforced by an import test).
