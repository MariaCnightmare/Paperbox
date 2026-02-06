from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple

from .constants import DB_FILENAME

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS docs (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  source_path TEXT NOT NULL,
  title       TEXT NOT NULL,
  sha256      TEXT NOT NULL UNIQUE,
  text        TEXT NOT NULL,
  created_at  TEXT NOT NULL
);

-- Full-text search over title+text
CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts
USING fts5(title, text, content='docs', content_rowid='id');

CREATE TRIGGER IF NOT EXISTS docs_ai AFTER INSERT ON docs BEGIN
  INSERT INTO docs_fts(rowid, title, text) VALUES (new.id, new.title, new.text);
END;

CREATE TRIGGER IF NOT EXISTS docs_ad AFTER DELETE ON docs BEGIN
  INSERT INTO docs_fts(docs_fts, rowid, title, text) VALUES('delete', old.id, old.title, old.text);
END;

CREATE TRIGGER IF NOT EXISTS docs_au AFTER UPDATE ON docs BEGIN
  INSERT INTO docs_fts(docs_fts, rowid, title, text) VALUES('delete', old.id, old.title, old.text);
  INSERT INTO docs_fts(rowid, title, text) VALUES (new.id, new.title, new.text);
END;
"""

@dataclass(frozen=True)
class Doc:
    id: int
    source_path: str
    title: str
    sha256: str
    text: str
    created_at: str

def project_db_path(project_dir: Path) -> Path:
    return project_dir / DB_FILENAME

def connect(project_dir: Path) -> sqlite3.Connection:
    project_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(project_db_path(project_dir)))
    conn.row_factory = sqlite3.Row
    return conn

def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()

def upsert_doc(conn: sqlite3.Connection, *, source_path: str, title: str, sha256: str, text: str, created_at: str) -> Tuple[int, bool]:
    """
    Returns (doc_id, inserted)
    """
    cur = conn.execute("SELECT id FROM docs WHERE sha256 = ?", (sha256,))
    row = cur.fetchone()
    if row:
        doc_id = int(row["id"])
        conn.execute(
            "UPDATE docs SET source_path=?, title=?, text=? WHERE id=?",
            (source_path, title, text, doc_id),
        )
        conn.commit()
        return doc_id, False

    cur = conn.execute(
        "INSERT INTO docs(source_path, title, sha256, text, created_at) VALUES (?,?,?,?,?)",
        (source_path, title, sha256, text, created_at),
    )
    conn.commit()
    return int(cur.lastrowid), True

def list_docs(conn: sqlite3.Connection) -> Sequence[Doc]:
    cur = conn.execute("SELECT * FROM docs ORDER BY id ASC")
    rows = cur.fetchall()
    return [Doc(**dict(r)) for r in rows]

def get_doc(conn: sqlite3.Connection, doc_id: int) -> Optional[Doc]:
    cur = conn.execute("SELECT * FROM docs WHERE id = ?", (doc_id,))
    row = cur.fetchone()
    if not row:
        return None
    return Doc(**dict(row))

def search_docs(conn: sqlite3.Connection, query: str, top: int = 10) -> Sequence[Tuple[Doc, float]]:
    # bm25: smaller is better; convert to score where larger is better
    cur = conn.execute(
        """
        SELECT d.*, bm25(docs_fts) AS bm25
        FROM docs_fts
        JOIN docs d ON docs_fts.rowid = d.id
        WHERE docs_fts MATCH ?
        ORDER BY bm25 ASC
        LIMIT ?
        """,
        (query, top),
    )
    rows = cur.fetchall()
    out = []
    for r in rows:
        bm25 = float(r["bm25"])
        score = 1.0 / (1.0 + max(bm25, 0.0))
        doc = Doc(
            id=int(r["id"]),
            source_path=str(r["source_path"]),
            title=str(r["title"]),
            sha256=str(r["sha256"]),
            text=str(r["text"]),
            created_at=str(r["created_at"]),
        )
        out.append((doc, score))
    return out
