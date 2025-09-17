from __future__ import annotations
import re
from typing import List, Tuple

from .models import Task, Workflow


def sentence_split(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+|;\s+", text.strip())
    parts = [p.strip() for p in parts if p]
    return parts


def normalize_task_name(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s[:120]


def build_graph(tasks: List[Task]) -> Tuple[dict[str, list[str]], dict[str, int]]:
    adj: dict[str, list[str]] = {t.id: [] for t in tasks}
    indeg: dict[str, int] = {t.id: 0 for t in tasks}
    for t in tasks:
        for d in t.depends_on:
            if d not in adj:
                continue
            adj[d].append(t.id)
            indeg[t.id] = indeg.get(t.id, 0) + 1
    return adj, indeg


def topo_sort(tasks: List[Task]) -> Tuple[List[str], List[str]]:
    adj, indeg = build_graph(tasks)
    q = [n for n, deg in indeg.items() if deg == 0]
    order: List[str] = []
    while q:
        n = q.pop(0)
        order.append(n)
        for m in adj.get(n, []):
            indeg[m] -= 1
            if indeg[m] == 0:
                q.append(m)
    issues: List[str] = []
    if len(order) != len(tasks):
        issues.append("Cycle detected or missing dependencies.")
    return order, issues


def validate_workflow(wf: Workflow) -> list[str]:
    issues: list[str] = []
    # Duplicate IDs
    ids = [t.id for t in wf.tasks]
    seen_ids = set()
    dup_ids = {i for i in ids if i in seen_ids or seen_ids.add(i)}
    if dup_ids:
        issues.append(f"Duplicate task IDs: {sorted(list(dup_ids))}")

    idset = set(ids)
    # Missing dependency ids and other per-task checks
    for t in wf.tasks:
        if not t.name or not str(t.name).strip():
            issues.append(f"Task {t.id} has empty name")
        if t.id in t.depends_on:
            issues.append(f"Task {t.id} depends on itself")
        if len(t.depends_on) != len(set(t.depends_on)):
            issues.append(f"Task {t.id} has duplicate dependencies")
        for d in t.depends_on:
            if d not in idset:
                issues.append(f"Task {t.id} depends on missing {d}")
    # At least one source and sink
    indeg = {t.id: 0 for t in wf.tasks}
    outdeg = {t.id: 0 for t in wf.tasks}
    for t in wf.tasks:
        for d in t.depends_on:
            indeg[t.id] += 1
            outdeg[d] += 1
    sources = [k for k, v in indeg.items() if v == 0]
    sinks = [k for k, v in outdeg.items() if v == 0]
    if not sources:
        issues.append("No source tasks (indegree 0)")
    if not sinks:
        issues.append("No sink tasks (outdegree 0)")
    return issues
