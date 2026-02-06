from __future__ import annotations

from pathlib import Path
from docx import Document

def extract_docx(path: Path) -> str:
    doc = Document(str(path))
    lines = []
    for p in doc.paragraphs:
        if p.text and p.text.strip():
            lines.append(p.text.strip())
    return "\n".join(lines).strip()
