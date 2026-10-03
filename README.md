# pdf-to-epub

Convert light-novel PDFs to EPUB through an editable DOCX intermediate format:
`pdf -> clean.pdf -> docx -> epub`.

The DOCX is the intervention point where headers, footers, page numbers and other PDF
noise are cleaned; the EPUB is then generated in pure Python with the original PDF
metadata and illustrations.

## Quickstart

```bash
uv sync
uv run pdf-to-epub convert "novel.pdf" -o novel.epub
```

By default only the EPUB remains after a successful run. Pass `--keep-intermediate` to keep
`<novel>.clean.pdf` and `<novel>.docx` for inspection/editing (`.docx` opens in
Word/LibreOffice).

## Common options

```bash
uv run pdf-to-epub convert novel.pdf \
  --workdir ./work \
  --title "Overridden title" \
  --author "Author Name" \
  --language es \
  --cover cover.jpg \
  --keep-intermediate
```

See `docs/uso.md` for the full option reference and `docs/arquitectura.md` for how the
pipeline works.

## Development

```bash
uv run pytest -q      # tests (no network, synthetic fixtures)
uv run ruff check .   # lint
```
