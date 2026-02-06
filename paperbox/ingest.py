from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from . import db
from .extractors import get_extractor
from .utils import guess_title, iter_files, normalize_whitespace, sha256_file

SUPPORTED_EXTS = {".pdf",".docx",".html",".htm",".txt",".md",".rst"}

@dataclass(frozen=True)
class IngestItemResult:
    path: Path
    skipped: bool
    reason: str
    doc_id: Optional[int] = None
    inserted: Optional[bool] = None

def ingest_paths(project_dir: Path, inputs: Sequence[Path]) -> List[IngestItemResult]:
    conn = db.connect(project_dir)
    db.init_db(conn)

    results: List[IngestItemResult] = []
    for path in iter_files(inputs):
        if path.suffix.lower() not in SUPPORTED_EXTS:
            results.append(IngestItemResult(path=path, skipped=True, reason="unsupported extension"))
            continue

        extractor = get_extractor(path)
        if extractor is None:
            results.append(IngestItemResult(path=path, skipped=True, reason="no extractor"))
            continue

        try:
            h = sha256_file(path)
        except Exception as e:
            results.append(IngestItemResult(path=path, skipped=True, reason=f"hash failed: {e}"))
            continue

        try:
            raw = extractor(path)
            text = normalize_whitespace(raw)
        except Exception as e:
            results.append(IngestItemResult(path=path, skipped=True, reason=f"extract failed: {e}"))
            continue

        if not text.strip():
            results.append(IngestItemResult(path=path, skipped=True, reason="empty text (maybe scanned PDF?)"))
            continue

        title = guess_title(path, text)
        created_at = _dt.datetime.now().isoformat(timespec="seconds")
        doc_id, inserted = db.upsert_doc(
            conn,
            source_path=str(path.resolve()),
            title=title,
            sha256=h,
            text=text,
            created_at=created_at,
        )
        results.append(IngestItemResult(path=path, skipped=False, reason="ok", doc_id=doc_id, inserted=inserted))

    conn.close()
    return results
