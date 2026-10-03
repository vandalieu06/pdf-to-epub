"""Repair paragraph boundaries produced by `pdf2docx`.

Two artifacts are corrected here:

- Several logical paragraphs (dialogue lines) crammed into one paragraph separated by
  ``w:br``/``w:cr`` elements: split them back into paragraphs when the line before ends a
  sentence or the line after starts with a quote/dash; otherwise the break is a line wrap
  and becomes a space.
- A logical paragraph split across pages: when the previous paragraph does not end a
  sentence and the next starts with a lowercase letter, merge them.

Formatting (bold/italic runs, paragraph properties) is preserved; headings, empty
paragraphs and paragraphs containing pictures are left untouched.
"""

from __future__ import annotations

import copy
import re

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from ..models import ReflowReport

_W_P = qn("w:p")
_W_PPR = qn("w:pPr")
_W_R = qn("w:r")
_W_RPR = qn("w:rPr")
_W_T = qn("w:t")
_W_TAB = qn("w:tab")
_W_BR = qn("w:br")
_W_CR = qn("w:cr")
_W_HYPERLINK = qn("w:hyperlink")
_W_DRAWING = qn("w:drawing")
_W_PICT = qn("w:pict")

TERMINALS = set('.!?…:;"»)\u201d')
LINESTARTS = set("\"'\u201c\u2018«-—")

QUOTE_CLOSING = "\u201d\"\u00bb'\u2019"
QUOTE_OPENING = "\u201c\"\u00ab'\u2018"
_QUOTE_SPLIT_RE = re.compile(
    rf"(?<=[{re.escape(QUOTE_CLOSING)}])\s{{1,3}}(?=[{re.escape(QUOTE_OPENING)}])"
)


def _is_heading(paragraph: Paragraph) -> bool:
    name = paragraph.style.name if paragraph.style is not None else ""
    return bool(name) and (name.startswith("Heading") or name == "Title")


def _has_image(paragraph: Paragraph) -> bool:
    element = paragraph._p
    return element.find(".//" + _W_DRAWING) is not None or element.find(
        ".//" + _W_PICT
    ) is not None


def _has_break(element: object) -> bool:
    return (
        element.find(".//" + _W_BR) is not None
        or element.find(".//" + _W_CR) is not None
    )


def _element_text(element: object) -> str:
    if element.tag == _W_T:
        return element.text or ""
    if element.tag == _W_TAB:
        return "\t"
    if element.tag in (_W_BR, _W_CR):
        return "\n"
    return "".join(_element_text(child) for child in element)


def _space_run() -> object:
    run = OxmlElement("w:r")
    text = OxmlElement("w:t")
    text.set(qn("xml:space"), "preserve")
    text.text = " "
    run.append(text)
    return run


def _run_has_content(run: object) -> bool:
    return any(child.tag != _W_RPR for child in run)


def _split_run(run: object) -> list[tuple[str, object | None]]:
    """Split a run into tokens: ("run", element) pieces and ("br", None)."""
    rpr = run.find(_W_RPR)
    tokens: list[tuple[str, object | None]] = []

    def new_run() -> object:
        element = OxmlElement("w:r")
        if rpr is not None:
            element.append(copy.deepcopy(rpr))
        return element

    current = None
    for child in list(run):
        if child.tag == _W_RPR:
            continue
        if child.tag in (_W_BR, _W_CR):
            if current is not None and _run_has_content(current):
                tokens.append(("run", current))
            tokens.append(("br", None))
            current = new_run()
        else:
            if current is None:
                current = new_run()
            current.append(child)
    if current is not None and _run_has_content(current):
        tokens.append(("run", current))
    return tokens


def _collect_tokens(element: object) -> list[tuple[str, object | None]]:
    tokens: list[tuple[str, object | None]] = []
    for child in element:
        if child.tag == _W_PPR:
            continue
        if child.tag == _W_R:
            tokens.extend(_split_run(child))
        elif child.tag == _W_HYPERLINK:
            tokens.append(("run", child))
    return tokens


def _should_split(left: str, right: str) -> bool:
    left = left.rstrip()
    right = right.lstrip()
    if not left or not right:
        return False
    return left[-1] in TERMINALS or right[0] in LINESTARTS


def _split_paragraph(paragraph: Paragraph) -> int:
    """Split a paragraph at dialogue/sentence breaks; return the resulting count."""
    element = paragraph._p
    if not _has_break(element):
        return 1

    tokens = _collect_tokens(element)
    ppr = element.find(_W_PPR)
    segments: list[list[object]] = [[]]
    texts: list[str] = [""]

    index = 0
    while index < len(tokens):
        kind, token = tokens[index]
        if kind == "br":
            look = index + 1
            right = ""
            while look < len(tokens) and tokens[look][0] == "run":
                right += _element_text(tokens[look][1])
                look += 1
            if _should_split(texts[-1], right):
                segments.append([])
                texts.append("")
            elif texts[-1].endswith((" ", "\t")):
                pass
            else:
                space = _space_run()
                segments[-1].append(space)
                texts[-1] += " "
        else:
            segments[-1].append(token)
            texts[-1] += _element_text(token)
        index += 1

    new_paragraphs: list[object] = []
    for segment, text in zip(segments, texts, strict=True):
        if not text.strip():
            continue
        new_p = OxmlElement("w:p")
        if ppr is not None:
            new_p.append(copy.deepcopy(ppr))
        for child in segment:
            new_p.append(child)
        new_paragraphs.append(new_p)

    if not new_paragraphs:
        return 1

    for new_p in new_paragraphs:
        element.addprevious(new_p)
    parent = element.getparent()
    if parent is not None:
        parent.remove(element)
    return len(new_paragraphs)


def _ends_with_closing_quote(text: str) -> bool:
    stripped = text.rstrip()
    return bool(stripped) and stripped[-1] in QUOTE_CLOSING


def _starts_with_opening_quote(text: str) -> bool:
    stripped = text.lstrip()
    return bool(stripped) and stripped[0] in QUOTE_OPENING


def _clone_run_with_text(run: object, text: str) -> object:
    clone = OxmlElement("w:r")
    rpr = run.find(_W_RPR)
    if rpr is not None:
        clone.append(copy.deepcopy(rpr))
    node = OxmlElement("w:t")
    node.set(qn("xml:space"), "preserve")
    node.text = text
    clone.append(node)
    return clone


def _trim_leading_space(run: object) -> None:
    for child in run:
        if child.tag == _W_T and child.text:
            child.text = child.text.lstrip()
            return
        if child.tag not in (_W_T, _W_RPR):
            return


def _trim_trailing_space(segment: list[object]) -> None:
    for element in reversed(segment):
        if element.tag != _W_R:
            return
        for child in reversed(list(element)):
            if child.tag == _W_T and child.text:
                child.text = child.text.rstrip()
                if child.text:
                    return
            elif child.tag not in (_W_T, _W_RPR):
                return


def _split_quote_paragraph(element: object) -> int:
    """Split where a closing quote is immediately followed by an opening quote."""
    ppr = element.find(_W_PPR)
    segments: list[list[object]] = [[]]
    previous_text = ""

    for child in list(element):
        if child.tag == _W_PPR:
            continue
        if child.tag != _W_R:
            segments[-1].append(child)
            previous_text = _element_text(child)
            continue
        text = _element_text(child)
        pieces = _QUOTE_SPLIT_RE.split(text) if _QUOTE_SPLIT_RE.search(text) else [text]
        if len(pieces) == 1:
            if _ends_with_closing_quote(previous_text) and _starts_with_opening_quote(text):
                _trim_trailing_space(segments[-1])
                segments.append([])
                _trim_leading_space(child)
            segments[-1].append(child)
            previous_text = text
        else:
            for index, piece in enumerate(pieces):
                if index > 0:
                    segments.append([])
                segments[-1].append(_clone_run_with_text(child, piece))
                previous_text = piece

    if len(segments) == 1:
        return 1

    new_paragraphs: list[object] = []
    for segment in segments:
        if not any(_element_text(item).strip() for item in segment):
            continue
        new_p = OxmlElement("w:p")
        if ppr is not None:
            new_p.append(copy.deepcopy(ppr))
        for item in segment:
            new_p.append(item)
        new_paragraphs.append(new_p)

    if not new_paragraphs:
        return 1
    for new_p in new_paragraphs:
        element.addprevious(new_p)
    parent = element.getparent()
    if parent is not None:
        parent.remove(element)
    return len(new_paragraphs)


def _is_continuation(previous: str, current: str) -> bool:
    left = previous.rstrip()
    right = current.lstrip()
    if not left or not right:
        return False
    if left[-1] in TERMINALS:
        return False
    if right[0] in LINESTARTS:
        return False
    return right[0].islower()


def _merge_paragraph(previous: Paragraph, current: Paragraph) -> None:
    previous_element = previous._p
    current_element = current._p
    if not previous.text.endswith((" ", "\t")):
        previous_element.append(_space_run())
    for child in list(current_element):
        if child.tag == _W_PPR:
            continue
        previous_element.append(child)
    _remove_paragraph(current)


def _remove_paragraph(paragraph: Paragraph) -> None:
    element = paragraph._p
    parent = element.getparent()
    if parent is not None:
        parent.remove(element)


def _skippable(paragraph: Paragraph) -> bool:
    return _is_heading(paragraph) or _has_image(paragraph)


def _merge_continuations(document: Document) -> int:
    """Merge a paragraph into the next non-empty paragraph when it continues it.

    Empty paragraphs between the two are removed; headings and paragraphs with images
    act as barriers. A single forward pass keeps this linear.
    """
    merged = 0
    paragraphs = document.paragraphs
    index = 0
    while index < len(paragraphs):
        previous = paragraphs[index]
        if _skippable(previous) or not previous.text.strip():
            index += 1
            continue
        look = index + 1
        while (
            look < len(paragraphs)
            and not paragraphs[look].text.strip()
            and not _skippable(paragraphs[look])
        ):
            look += 1
        if look >= len(paragraphs):
            index += 1
            continue
        current = paragraphs[look]
        if _skippable(current):
            index = look
            continue
        if not _is_continuation(previous.text, current.text):
            index += 1
            continue
        for empty_index in range(look - 1, index, -1):
            _remove_paragraph(paragraphs[empty_index])
        del paragraphs[index + 1 : look + 1]
        _merge_paragraph(previous, current)
        merged += 1
    return merged


def reflow_document(document: Document) -> ReflowReport:
    """Split dialogue breaks and merge page-break continuations."""
    report = ReflowReport()

    for paragraph in list(document.paragraphs):
        if _skippable(paragraph):
            continue
        created = _split_paragraph(paragraph)
        report.split_paragraphs += max(0, created - 1)

    for paragraph in list(document.paragraphs):
        if _skippable(paragraph):
            continue
        created = _split_quote_paragraph(paragraph._p)
        report.split_paragraphs += max(0, created - 1)

    report.merged_paragraphs = _merge_continuations(document)
    return report
