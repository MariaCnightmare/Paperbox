from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Sequence, Tuple

import numpy as np

@dataclass(frozen=True)
class Node:
    id: int
    label: str

@dataclass(frozen=True)
class Edge:
    a: int
    b: int
    weight: float

def build_edges(sim: np.ndarray, threshold: float) -> List[Edge]:
    n = sim.shape[0]
    edges: List[Edge] = []
    for i in range(n):
        for j in range(i+1, n):
            w = float(sim[i, j])
            if w >= threshold:
                edges.append(Edge(a=i, b=j, weight=w))
    # sort strong first
    edges.sort(key=lambda e: e.weight, reverse=True)
    return edges

def render_mermaid(nodes: Sequence[Node], edges: Sequence[Edge]) -> str:
    lines = ["```mermaid", "graph TD"]
    for nd in nodes:
        lines.append(f'  D{nd.id}["{nd.label}"]')
    for e in edges:
        lines.append(f'  D{e.a} ---|{e.weight:.2f}| D{e.b}')
    lines.append("```")
    return "\n".join(lines)

def render_dot(nodes: Sequence[Node], edges: Sequence[Edge]) -> str:
    lines = ["graph G {", '  graph [overlap=false, splines=true];', '  node [shape=box];']
    for nd in nodes:
        safe = nd.label.replace('"', '\"')
        lines.append(f'  D{nd.id} [label="{safe}"];')
    for e in edges:
        lines.append(f'  D{e.a} -- D{e.b} [label="{e.weight:.2f}", penwidth={(1.0 + 4.0*e.weight):.2f}];')
    lines.append("}")
    return "\n".join(lines)

def render(nodes: Sequence[Node], edges: Sequence[Edge], fmt: Literal["mermaid","dot"]) -> str:
    if fmt == "dot":
        return render_dot(nodes, edges)
    return render_mermaid(nodes, edges)
