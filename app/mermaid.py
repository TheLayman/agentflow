from __future__ import annotations

from .models import Workflow


def to_mermaid(wf: Workflow, direction: str = "TD") -> str:
    # Build edges from depends_on if edges not provided
    edges = set()
    for t in wf.tasks:
        for d in t.depends_on:
            edges.add((d, t.id))

    # Header
    out = [f"graph {direction}"]
    # Nodes
    for t in wf.tasks:
        label = t.name.replace("\"", "'")
        out.append(f"  {t.id}[\"{label}\"]")
    # Edges
    for a, b in sorted(edges):
        out.append(f"  {a} --> {b}")
    return "\n".join(out)

