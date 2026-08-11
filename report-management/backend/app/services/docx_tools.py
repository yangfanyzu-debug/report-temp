from __future__ import annotations

import zipfile
from pathlib import Path

from docx import Document


DOCX_MARKERS = {"[Content_Types].xml", "word/document.xml"}


def is_docx(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            return DOCX_MARKERS.issubset(archive.namelist())
    except (OSError, zipfile.BadZipFile):
        return False


def extract_text_and_tables(path: Path) -> dict[str, object]:
    document = Document(path)
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    tables: list[list[list[str]]] = []
    for table in document.tables:
        rows: list[list[str]] = []
        for row in table.rows:
            rows.append([cell.text.strip() for cell in row.cells])
        tables.append(rows)

    return {
        "paragraphs": paragraphs,
        "tables": tables,
        "tableCount": len(tables),
        "paragraphCount": len(paragraphs),
    }
