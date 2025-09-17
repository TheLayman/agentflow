from __future__ import annotations
from openai import OpenAI
from pydantic import BaseModel, ConfigDict
import os
import re
import logging
from typing import List, Tuple, Dict, Any
from .models import Task, Workflow, DecomposeRequest
from .utils import sentence_split, normalize_task_name

logger = logging.getLogger("workflow.decompose")

def fallback_decomposition(req: DecomposeRequest) -> Workflow:
    logger.info("Using fallback decomposition (granularity=%s)", req.granularity)
    raw_sentences = sentence_split(req.text)
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
        title = normalize_task_name(sent)
        depends = [prev_id] if prev_id else []
        
        # Determine if this should be a human or agent task based on keywords
        is_human_task = any(keyword in sent.lower() for keyword in 
                          ['review', 'approve', 'verify', 'check', 'validate', 'decision', 'judge'])
        
        actor = "human" if is_human_task else "agent"
        tool = None if is_human_task else "generic_tool"
        approval = "human" if is_human_task else "none"
        
        # Generate meaningful inputs/outputs based on task content
        def generate_meaningful_artifacts(task_text: str, task_id: str, is_output: bool = True):
            """Generate meaningful artifact names based on task content"""
            task_lower = task_text.lower()
            
            # Common patterns for different types of tasks (order matters)
            if any(word in task_lower for word in ['retrieve', 'fetch', 'get']) and 'email' in task_lower:
                return ['filtered_emails'] if is_output else ['time_window_config']
            elif any(word in task_lower for word in ['extract', 'parse']) and ('email' in task_lower or 'item' in task_lower):
                return ['actionable_items'] if is_output else ['filtered_emails']
            elif any(word in task_lower for word in ['consent', 'connection', 'access']):
                return ['access_credentials'] if is_output else ['user_permissions']
            elif any(word in task_lower for word in ['time', 'window', 'configuration', 'config']):
                return ['time_window_config'] if is_output else ['access_credentials']
            elif any(word in task_lower for word in ['database', 'schema', 'db']):
                return ['database_schema'] if is_output else ['requirements_spec']
            elif any(word in task_lower for word in ['api', 'endpoint', 'service']):
                return ['api_implementation'] if is_output else ['schema_definition']
            elif any(word in task_lower for word in ['auth', 'login', 'authentication']):
                return ['auth_system'] if is_output else ['api_framework']
            elif any(word in task_lower for word in ['test', 'testing']):
                return ['test_results'] if is_output else ['system_under_test']
            elif any(word in task_lower for word in ['deploy', 'deployment']):
                return ['deployed_system'] if is_output else ['tested_application']
            elif any(word in task_lower for word in ['review', 'validate', 'check']):
                return ['approval_decision'] if is_output else ['review_materials']
            elif any(word in task_lower for word in ['security', 'policy', 'policies']):
                return ['security_approval'] if is_output else ['security_documentation']
            else:
                # More descriptive generic fallback
                action_words = task_text.split()[:2] if task_text.split() else ['task']
                action_desc = '_'.join(word.lower() for word in action_words)
                return [f'{action_desc}_result'] if is_output else [f'{action_desc}_input']
        
        # Generate context-aware inputs and outputs
        if prev_id:
            # Use the previous task's output as input
            prev_task_text = sentences[i-2] if i > 1 else "initial requirements"
            inputs = generate_meaningful_artifacts(prev_task_text, prev_id, is_output=True)
        else:
            inputs = ["project_requirements"]
        
        outputs = generate_meaningful_artifacts(sent, tid, is_output=True)
        
        acceptance_criteria = [f"Task {tid} completed successfully"]
        
        tasks.append(Task(
            id=tid,
            title=title,
            actor=actor,
            depends_on=[d for d in depends if d],
            inputs=inputs,
            outputs=outputs,
            tool=tool,
            parameters=None,  # Use None instead of empty dict
            approval=approval,
            acceptance_criteria=acceptance_criteria,
            parallelizable=False,
            # Legacy compatibility
            name=title,
            description=None
        ))
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
        class ParsedWorkflow(BaseModel):
            title: str
            version: str | None = "0.1"
            assumptions: List[str] = []
            tasks: List[Task]

        client = OpenAI(api_key=api_key, base_url=os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1/")

        system_prompt = (
            "You are a workflow decomposition engine that outputs only JSON conforming to the provided schema. "
            "Goal: produce atomic, dependency-aware tasks suitable for software agents, with explicit human approval/verification gates where policy or risk requires it.\n\n"
            
            "Definitions:\n"
            "Atomic task: one actor, one primary tool (if agent), one clear action, one bounded effect. No hidden substeps. "
            "Each task must specify concrete inputs and produce concrete outputs. If an operation would need two different tools or two approvals, split it.\n"
            "Agent task: actor='agent', must include tool and any parameters.\n"
            "Human task: actor='human', typically approval='human' or used for judgment calls and verification steps.\n\n"
            
            "Constraints:\n"
            "Acyclic DAG: use ids T1..Tn. depends_on may reference only earlier ids; no cycles.\n"
            "Topological order: list tasks in executable order.\n"
            "Interfaces, not vibes: every task has explicit inputs and outputs. Outputs of predecessors should satisfy the inputs of dependents.\n"
            "Approvals & verification: insert human gates where legality, risk, or policy demands; set approval accordingly and express objective acceptance_criteria.\n"
            "Automation first: prefer actor='agent' when a reliable tool/API exists and acceptance criteria can be machine-checked.\n"
            "Parallelism: set parallelizable=true only if the task has no unresolved dependencies and no shared mutable artifact that would race.\n"
            "Naming: title starts with a strong verb (e.g., 'Extract…', 'Validate…', 'Generate…', 'Route…').\n\n"
            
            "Atomicity heuristics:\n"
            "One actor • One tool • One key artifact • One decision.\n"
            "Can be implemented as a single API call or bounded human action; if not, split.\n"
            "Each task's outputs should be immediately usable as another task's inputs or as a final deliverable.\n\n"
            
            "Quality bar:\n"
            "No generic outputs ('processed data'); use concrete names ('extracted_parties.json').\n"
            "No ambiguous verbs ('handle', 'manage'); prefer precise actions.\n"
            "Use approval='human' for legal/judgment checkpoints; include objective acceptance criteria.\n"
            "Return only JSON (no code fences), strictly matching the schema."
        )
        user_prompt = (
            f"Process: {req.text}\n"
            f"Granularity target: atomic (single actor, single tool, single action).\n"
            f"Risk policy: insert human approvals for legal/contractual commitments, PII handling, or irreversible changes.\n"
            f"Available tools/APIs: discover if obvious.\n"
            f"Output artifacts required at the end: to be determined from process.\n"
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

