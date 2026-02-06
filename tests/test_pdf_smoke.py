from __future__ import annotations

from pathlib import Path
import tempfile

import pytest

from paperbox.ingest import ingest_paths
from paperbox import db


def _make_pdf(path: Path) -> None:
    # reportlab is optional (dev extra)
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(path))
    c.drawString(72, 720, "Paperbox PDF smoke test: systems and causality.")
    c.save()


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("reportlab") is None,
    reason="reportlab not installed",
)
def test_pdf_smoke():
    with tempfile.TemporaryDirectory() as td:
        project = Path(td) / "proj"
        project.mkdir()
        pdf = Path(td) / "a.pdf"
        _make_pdf(pdf)

        res = ingest_paths(project, [pdf])
        assert len(res) == 1
        assert res[0].skipped is False

        conn = db.connect(project)
        db.init_db(conn)
        hits = db.search_docs(conn, "cau*", top=5)
        conn.close()
        assert len(hits) >= 1

