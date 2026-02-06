from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from . import db
from .graphing import Node, build_edges, render as render_graph
from .ingest import ingest_paths
from .nlp import compare_texts, pairwise_similarity, summarize

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()

def _p(p: Optional[Path]) -> Path:
    return Path(p) if p else Path(".")

@app.command()
def init(project: Path = typer.Argument(..., help="Project directory (workspace)")):
    """Initialize a project workspace (creates SQLite DB)."""
    conn = db.connect(project)
    db.init_db(conn)
    conn.close()
    console.print(Panel.fit(f"[bold green]OK[/] initialized: {project.resolve()}"))

@app.command()
def ingest(
    path: Path = typer.Argument(..., help="File or directory to ingest"),
    project: Path = typer.Option(..., "--project", "-p", help="Project directory"),
):
    """Ingest a file or directory; extract text and index into SQLite FTS."""
    results = ingest_paths(project, [path])
    table = Table(title="Ingest results")
    table.add_column("Path", overflow="fold")
    table.add_column("Status", style="bold")
    table.add_column("DocID", justify="right")
    table.add_column("Note", overflow="fold")
    for r in results:
        status = "SKIP" if r.skipped else ("NEW" if r.inserted else "UPD")
        style = "yellow" if r.skipped else ("green" if r.inserted else "cyan")
        table.add_row(str(r.path), f"[{style}]{status}[/{style}]", str(r.doc_id or "-"), r.reason)
    console.print(table)

@app.command()
def list(project: Path = typer.Option(..., "--project", "-p", help="Project directory")):
    """List ingested documents."""
    conn = db.connect(project)
    db.init_db(conn)
    docs = db.list_docs(conn)
    conn.close()

    table = Table(title="Documents")
    table.add_column("ID", justify="right")
    table.add_column("Title", overflow="fold")
    table.add_column("Created")
    table.add_column("Source", overflow="fold")
    for d in docs:
        table.add_row(str(d.id), d.title, d.created_at, d.source_path)
    console.print(table)

@app.command()
def view(
    doc_id: int = typer.Argument(..., help="Document ID"),
    project: Path = typer.Option(..., "--project", "-p", help="Project directory"),
    head: int = typer.Option(80, "--head", help="Show first N lines"),
):
    """View extracted text (first N lines)."""
    conn = db.connect(project)
    db.init_db(conn)
    doc = db.get_doc(conn, doc_id)
    conn.close()
    if not doc:
        raise typer.Exit(code=1)

    lines = doc.text.splitlines()
    shown = "\n".join(lines[:head])
    console.print(Panel(shown, title=f"{doc.id}: {doc.title}", subtitle=f"{doc.source_path}"))

@app.command()
def search(
    query: str = typer.Argument(..., help="FTS query (SQLite FTS5 syntax)"),
    project: Path = typer.Option(..., "--project", "-p", help="Project directory"),
    top: int = typer.Option(10, "--top", help="Top N results"),
):
    """Search documents by full-text (SQLite FTS5)."""
    conn = db.connect(project)
    db.init_db(conn)
    hits = db.search_docs(conn, query, top=top)
    conn.close()

    table = Table(title=f"Search: {query}")
    table.add_column("Rank", justify="right")
    table.add_column("ID", justify="right")
    table.add_column("Score", justify="right")
    table.add_column("Title", overflow="fold")
    for i, (doc, score) in enumerate(hits, start=1):
        table.add_row(str(i), str(doc.id), f"{score:.3f}", doc.title)
    console.print(table)

@app.command()
def summarize_cmd(
    doc_id: int = typer.Argument(..., help="Document ID"),
    project: Path = typer.Option(..., "--project", "-p", help="Project directory"),
    sentences: int = typer.Option(7, "--sentences", "-n", help="Number of sentences"),
):
    """Summarize a document (local frequency-based)."""
    conn = db.connect(project)
    db.init_db(conn)
    doc = db.get_doc(conn, doc_id)
    conn.close()
    if not doc:
        raise typer.Exit(code=1)

    out = summarize(doc.text, sentences=sentences)
    console.print(Panel(out or "(empty)", title=f"Summary: {doc.id}: {doc.title}"))

# Expose as "summarize" command name
app.command(name="summarize")(summarize_cmd)

@app.command()
def compare(
    doc_id1: int = typer.Argument(..., help="Document ID 1"),
    doc_id2: int = typer.Argument(..., help="Document ID 2"),
    project: Path = typer.Option(..., "--project", "-p", help="Project directory"),
    top_terms: int = typer.Option(15, "--top-terms", help="Top terms per bucket"),
):
    """Compare two documents: similarity + common terms + unique terms."""
    conn = db.connect(project)
    db.init_db(conn)
    d1 = db.get_doc(conn, doc_id1)
    d2 = db.get_doc(conn, doc_id2)
    conn.close()
    if not d1 or not d2:
        raise typer.Exit(code=1)

    r = compare_texts(d1.text, d2.text, top_terms=top_terms)

    console.print(Panel(f"[bold]Cosine similarity[/]: {r.similarity:.3f}\n\n"
                        f"[bold]Doc1[/]: {d1.title}\n[bold]Doc2[/]: {d2.title}",
                        title="Compare"))

    def term_table(title: str, items):
        t = Table(title=title)
        t.add_column("Term", overflow="fold")
        t.add_column("Weight", justify="right")
        for term, w in items:
            t.add_row(term, f"{w:.4f}")
        console.print(t)

    term_table("Common terms", r.common_terms)
    term_table(f"Doc1 unique terms (ID {d1.id})", r.doc1_unique_terms)
    term_table(f"Doc2 unique terms (ID {d2.id})", r.doc2_unique_terms)

@app.command()
def graph(
    project: Path = typer.Option(..., "--project", "-p", help="Project directory"),
    threshold: float = typer.Option(0.25, "--threshold", help="Edge threshold for similarity"),
    format: str = typer.Option("mermaid", "--format", help="mermaid or dot"),
    max_nodes: int = typer.Option(60, "--max-nodes", help="Limit nodes to avoid huge graphs"),
):
    """Build a similarity graph across all docs; output Mermaid or DOT."""
    fmt = format.lower()
    if fmt not in ("mermaid", "dot"):
        raise typer.Exit(code=2)

    conn = db.connect(project)
    db.init_db(conn)
    docs = db.list_docs(conn)
    conn.close()

    if not docs:
        console.print("[yellow]No docs found.[/]")
        raise typer.Exit(code=0)

    docs = docs[:max_nodes]
    texts = [d.text for d in docs]
    sim = pairwise_similarity(texts)

    nodes = [Node(id=i, label=f"{docs[i].id}: {docs[i].title}") for i in range(len(docs))]
    edges = build_edges(sim, threshold=threshold)
    out = render_graph(nodes, edges, fmt=fmt)  # type: ignore[arg-type]
    console.print(out)
