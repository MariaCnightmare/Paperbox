from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable

_JP_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]")

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def is_probably_japanese(text: str, threshold: float = 0.08) -> bool:
    if not text:
        return False
    jp = len(_JP_RE.findall(text))
    return (jp / max(len(text), 1)) >= threshold

def normalize_whitespace(text: str) -> str:
    # collapse spaces but keep newlines
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # remove excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # trim each line
    lines = [ln.strip() for ln in text.split("\n")]
    return "\n".join(lines).strip()

def guess_title(path: Path, text: str) -> str:
    # prefer first non-empty line that isn't too long
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if len(s) > 140:
            continue
        # Avoid lines that are mostly punctuation
        if sum(ch.isalnum() for ch in s) < 3:
            continue
        return s
    return path.stem

def iter_files(paths: Iterable[Path]) -> Iterable[Path]:
    for p in paths:
        if p.is_dir():
            for child in p.rglob("*"):
                if child.is_file():
                    yield child
        elif p.is_file():
            yield p
