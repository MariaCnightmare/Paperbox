from __future__ import annotations

import sys
from pathlib import Path


def _ensure_repo_on_path() -> None:
    try:
        import paperbox  # noqa: F401
        return
    except ModuleNotFoundError:
        repo_root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(repo_root))


_ensure_repo_on_path()
