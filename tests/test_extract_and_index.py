from __future__ import annotations

from pathlib import Path
import tempfile

from paperbox import db
from paperbox.ingest import ingest_paths

def test_ingest_txt_and_search():
    with tempfile.TemporaryDirectory() as td:
        project = Path(td) / "proj"
        project.mkdir()

        sample = Path(td) / "a.txt"
        sample.write_text("Causality in social systems. Communication is selection.\n", encoding="utf-8")

        res = ingest_paths(project, [sample])
        assert len(res) == 1
        assert res[0].skipped is False

        conn = db.connect(project)
        db.init_db(conn)
        hits = db.search_docs(conn, "Causality", top=5)
        conn.close()
        assert len(hits) >= 1
        assert hits[0][0].title
