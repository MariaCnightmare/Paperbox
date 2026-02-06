from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, Optional

from .pdf import extract_pdf
from .docx import extract_docx
from .html import extract_html
from .text import extract_text

Extractor = Callable[[Path], str]

def get_extractor(path: Path) -> Optional[Extractor]:
    ext = path.suffix.lower()
    mapping: Dict[str, Extractor] = {
        ".pdf": extract_pdf,
        ".docx": extract_docx,
        ".html": extract_html,
        ".htm": extract_html,
        ".txt": extract_text,
        ".md": extract_text,
        ".rst": extract_text,
    }
    return mapping.get(ext)
