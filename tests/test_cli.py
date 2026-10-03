from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from pdf_to_epub import __version__
from pdf_to_epub.cli import app
from pdf_to_epub.core.errors import DocxStageError, EpubStageError, PdfStageError
from pdf_to_epub.core.models import ConversionReport

runner = CliRunner()


def _fake_report(input_pdf: Path, output: Path) -> ConversionReport:
    return ConversionReport(
        input_pdf=input_pdf,
        output_epub=output,
        chapters=2,
        images_embedded=1,
        header_footer_removals=4,
        elapsed_s=0.5,
    )


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_missing_argument_is_usage_error() -> None:
    result = runner.invoke(app, ["convert"])
    assert result.exit_code == 2


def test_missing_input_is_validation_error(tmp_path: Path) -> None:
    result = runner.invoke(app, ["convert", str(tmp_path / "nope.pdf")])
    assert result.exit_code == 1


def test_success_exit_zero(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    pdf = tmp_path / "in.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    output = tmp_path / "out.epub"

    def fake_run(options, *, progress=None):  # type: ignore[no-untyped-def]
        return _fake_report(options.input_pdf, output)

    monkeypatch.setattr("pdf_to_epub.cli.run", fake_run)
    result = runner.invoke(app, ["convert", str(pdf), "-o", str(output)])
    assert result.exit_code == 0
    assert str(output) in result.stdout


def test_quiet_success_has_no_stdout(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    pdf = tmp_path / "in.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    def fake_run(options, *, progress=None):  # type: ignore[no-untyped-def]
        return _fake_report(options.input_pdf, tmp_path / "out.epub")

    monkeypatch.setattr("pdf_to_epub.cli.run", fake_run)
    result = runner.invoke(app, ["convert", str(pdf), "--quiet"])
    assert result.exit_code == 0
    assert result.stdout == ""


def _raising(error: Exception):  # type: ignore[no-untyped-def]
    def fake_run(options, *, progress=None):  # type: ignore[no-untyped-def]
        raise error

    return fake_run


def test_image_options_reach_conversion(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    pdf = tmp_path / "in.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    captured: dict[str, object] = {}

    def fake_run(options, *, progress=None):  # type: ignore[no-untyped-def]
        captured["image_quality"] = options.image_quality
        captured["keep_original_images"] = options.keep_original_images
        captured["use_pdf_images"] = options.use_pdf_images
        return _fake_report(options.input_pdf, tmp_path / "out.epub")

    monkeypatch.setattr("pdf_to_epub.cli.run", fake_run)
    result = runner.invoke(
        app,
        [
            "convert",
            str(pdf),
            "--image-quality",
            "70",
            "--keep-original-images",
            "--keep-docx-images",
        ],
    )
    assert result.exit_code == 0
    assert captured == {
        "image_quality": 70,
        "keep_original_images": True,
        "use_pdf_images": False,
    }


def test_reflow_option_reaches_conversion(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    pdf = tmp_path / "in.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    captured: dict[str, object] = {}

    def fake_run(options, *, progress=None):  # type: ignore[no-untyped-def]
        captured["reflow_paragraphs"] = options.reflow_paragraphs
        return _fake_report(options.input_pdf, tmp_path / "out.epub")

    monkeypatch.setattr("pdf_to_epub.cli.run", fake_run)
    result = runner.invoke(app, ["convert", str(pdf), "--no-reflow"])
    assert result.exit_code == 0
    assert captured == {"reflow_paragraphs": False}


def test_keep_intermediate_option(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    pdf = tmp_path / "in.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    captured: dict[str, object] = {}

    def fake_run(options, *, progress=None):  # type: ignore[no-untyped-def]
        captured["keep"] = options.keep_intermediate
        return _fake_report(options.input_pdf, tmp_path / "out.epub")

    monkeypatch.setattr("pdf_to_epub.cli.run", fake_run)

    assert runner.invoke(app, ["convert", str(pdf)]).exit_code == 0
    assert captured["keep"] is False

    assert (
        runner.invoke(app, ["convert", str(pdf), "--keep-intermediate"]).exit_code == 0
    )
    assert captured["keep"] is True

    assert (
        runner.invoke(app, ["convert", str(pdf), "--clean-intermediate"]).exit_code == 0
    )
    assert captured["keep"] is False


def test_warns_about_ignored_pages(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    pdf = tmp_path / "in.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    def fake_run(options, *, progress=None):  # type: ignore[no-untyped-def]
        report = _fake_report(options.input_pdf, tmp_path / "out.epub")
        report.ignored_pages = [4]
        return report

    monkeypatch.setattr("pdf_to_epub.cli.run", fake_run)
    result = runner.invoke(app, ["convert", str(pdf)])
    assert result.exit_code == 0
    assert "ignored pages 4" in result.stdout


def test_exit_codes_for_stage_errors(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    pdf = tmp_path / "in.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    for error, expected in (
        (PdfStageError("pdf"), 3),
        (DocxStageError("docx"), 4),
        (EpubStageError("epub"), 5),
    ):
        monkeypatch.setattr("pdf_to_epub.cli.run", _raising(error))
        result = runner.invoke(app, ["convert", str(pdf)])
        assert result.exit_code == expected
