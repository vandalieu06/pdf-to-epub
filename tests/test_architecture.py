from __future__ import annotations

import ast
from pathlib import Path

CORE_DIR = Path(__file__).resolve().parents[1] / "src" / "pdf_to_epub" / "core"
FORBIDDEN = {"typer", "rich", "click"}


def test_core_does_not_import_presentation_libraries() -> None:
    offenders: list[str] = []
    for path in CORE_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in FORBIDDEN:
                        offenders.append(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] in FORBIDDEN:
                    offenders.append(f"{path.name}: from {node.module}")
    assert offenders == []
