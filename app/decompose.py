from __future__ import annotations
from openai import OpenAI
from pydantic import BaseModel, ConfigDict
import os
import re
import logging
from typing import List, Tuple, Dict, Any
from .models import Task, Workflow, DecomposeRequest

logger = logging.getLogger("workflow.decompose")

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
            logger.exception("LLM parse failed; falling back to heuristic: %s", parse_err)
            return None, None, {"llm_error": str(parse_err)}
        except Exception as e:
            logger.exception("LLM parse failed; falling back to heuristic: %s", e)
            return None, None, {"llm_error": str(e)}

    except Exception as e:
        logger.exception("LLM decomposition setup failed: %s", e)
        return None, None, {"llm_error": str(e)}

