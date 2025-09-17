from __future__ import annotations

import os
import re
import logging
import json
from typing import List, Tuple, Dict, Any

from .models import Task, Workflow, DecomposeRequest

logger = logging.getLogger("workflow.decompose")


def _sentence_split(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+|;\s+", text.strip())
    parts = [p.strip() for p in parts if p]
    return parts


def _normalize_task_name(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s[:120]


def fallback_decomposition(req: DecomposeRequest) -> Workflow:
    logger.info("Using fallback decomposition (granularity=%s)", req.granularity)
    raw_sentences = _sentence_split(req.text)
    if not raw_sentences:
        raw_sentences = [
            "Understand the goal",
            "Identify stakeholders",
            "Draft plan",
            "Execute",
            "Review results",
        ]

    sentences: List[str] = []
    for s in raw_sentences:
        if req.granularity == "high":
            subs = re.split(r",| and | then ", s, flags=re.IGNORECASE)
            subs = [sub.strip() for sub in subs if sub.strip()]
            sentences.extend(subs or [s])
        elif req.granularity == "low":
            sentences.append(s)
        else:
            if len(s) > 100:
                subs = re.split(r",| and | then ", s, maxsplit=1, flags=re.IGNORECASE)
                sentences.extend([x.strip() for x in subs if x.strip()])
            else:
                sentences.append(s)

    tasks: List[Task] = []
    prev_id: str | None = None
    for i, sent in enumerate(sentences, start=1):
        tid = f"T{i}"
        name = _normalize_task_name(sent)
        depends = [prev_id] if prev_id else []
        tasks.append(Task(id=tid, name=name, description=None, depends_on=[d for d in depends if d]))
        prev_id = tid

    title_src = sentences[0] if sentences else (req.title or "Workflow")
    wf = Workflow(
        title=req.title or (title_src[:40] + ("..." if len(title_src) > 40 else "")),
        tasks=tasks,
    )
    return wf


def try_llm_decomposition(req: DecomposeRequest) -> tuple[Workflow | None, str | None, Dict[str, Any] | None]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.info("OPENAI_API_KEY not set; skipping LLM decomposition")
        return None, None, None

    model = os.getenv("OPENAI_MODEL", "gpt-5")
    reasoning_effort = os.getenv("OPENAI_REASONING_EFFORT", "medium")

    try:
        from openai import OpenAI
        from pydantic import BaseModel, ConfigDict

        class ConstraintsStrict(BaseModel):
            model_config = ConfigDict(extra="forbid")
            roles: List[str]
            tools: List[str]
            compliance: List[str]
            sla: str
            departments: List[str]

        class ParsedWorkflow(BaseModel):
            title: str
            version: str | None = "0.1"
            constraints: ConstraintsStrict | None = None
            assumptions: List[str] = []
            tasks: List[Task]

        client = OpenAI(api_key=api_key, base_url=os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1/")

        system_prompt = (
            "You are a workflow decomposition engine. Produce granular, dependency-aware workflows. "
            "Ensure acyclic dependencies using task ids like T1..Tn only. "
            "If you include a constraints object, include all keys: roles, tools, compliance, sla, departments (use empty arrays or empty string if unknown)."
        )
        user_prompt = (
            f"Process: {req.text}\n"
            f"Granularity: {req.granularity}.\n"
            f"Title: {req.title or ''}"
        )
        # Track any parse error to surface in metadata on fallback path
        llm_error: str | None = None

        try:
            logger.info("Calling OpenAI responses.parse (model=%s)", model)
            resp = client.responses.parse(
                model=model,
                input=[
                    {"role": "system", "content": system_prompt + " Output only JSON without code fences."},
                    {"role": "user", "content": user_prompt},
                ],
                text_format=ParsedWorkflow,
                reasoning={"effort": reasoning_effort},
                max_output_tokens=12000,
            )
            parsed: ParsedWorkflow | None = getattr(resp, "output_parsed", None)
            if parsed is None:
                raise ValueError("responses.parse returned no parsed output")

            wf = Workflow(
                title=parsed.title,
                tasks=parsed.tasks,
                assumptions=parsed.assumptions or [],
                version=parsed.version or "0.1",
            )
            # Cleanup deps
            idset = {t.id for t in wf.tasks}
            for t in wf.tasks:
                deps = [d for d in t.depends_on if d in idset and d != t.id]
                seen = set()
                t.depends_on = [d for d in deps if not (d in seen or seen.add(d))]
            logger.info("LLM decomposition succeeded (tasks=%d, engine=responses-parse)", len(wf.tasks))
            return wf, "responses-parse", None
        except Exception as parse_err:
            logger.warning("responses.parse failed; attempting responses.create with JSON schema: %s", parse_err)
            llm_error = str(parse_err)
            # Minimal strict JSON Schema to reduce output size and avoid truncation
            strict_schema: Dict[str, Any] = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "id": {"type": "string"},
                                "name": {"type": "string"},
                                "depends_on": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["id", "name", "depends_on"],
                        },
                    },
                },
                "required": ["title", "tasks"],
            }

            resp2 = client.responses.create(
                model=model,
                instructions=(
                    "Return only valid JSON. Do not include code fences. "
                    "Output must match this minimal schema with only fields shown."
                ),
                input=(
                    f"Process: {req.text}\n"
                    f"Granularity: {req.granularity}.\n"
                    f"Title: {req.title or ''}"
                ),
                reasoning={"effort": reasoning_effort},
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "MinimalWorkflow",
                        "schema": strict_schema,
                        "strict": True,
                    }
                },
                max_output_tokens=12000,
                truncation="auto",
            )
            raw = getattr(resp2, "output_text", None)
            if not raw:
                out = getattr(resp2, "output", []) or []
                texts: List[str] = []
                for item in out:
                    if isinstance(item, dict) and item.get("type") == "message":
                        for c in item.get("content") or []:
                            if isinstance(c, dict) and c.get("type") in ("output_text", "text") and "text" in c:
                                texts.append(c["text"]) 
                raw = "\n".join(texts) if texts else None
            if not raw:
                raise RuntimeError("No text content in Responses API result")
            data = json.loads(raw)
            # Map minimal schema to our internal Workflow/Task structures
            tasks_objs: List[Task] = []
            for t in data.get("tasks", []):
                tasks_objs.append(
                    Task(
                        id=str(t.get("id")),
                        name=str(t.get("name")),
                        depends_on=[str(x) for x in (t.get("depends_on") or [])],
                    )
                )
            wf = Workflow(
                title=str(data.get("title", req.title or "Workflow")),
                tasks=tasks_objs,
                assumptions=[],
                version="0.1",
            )
            idset = {t.id for t in wf.tasks}
            for t in wf.tasks:
                deps = [d for d in t.depends_on if d in idset and d != t.id]
                seen = set()
                t.depends_on = [d for d in deps if not (d in seen or seen.add(d))]
            logger.info("LLM decomposition succeeded (tasks=%d, engine=responses-schema-min)", len(wf.tasks))
            return wf, "responses-schema-min", {"llm_error": llm_error, "llm_raw": raw}
        except Exception as e:
            logger.exception("LLM parse failed; falling back to heuristic: %s", e)
            return None, None, {"llm_error": str(e)}

    except ImportError as e:
        logger.info("OpenAI/Pydantic not installed; skipping LLM decomposition: %s", e)
        return None, None, {"llm_error": str(e)}
    except Exception as e:
        logger.exception("LLM decomposition setup failed: %s", e)
        return None, None, {"llm_error": str(e)}


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
