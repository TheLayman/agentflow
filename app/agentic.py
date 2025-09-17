from __future__ import annotations

import json
import logging
import os
from typing import List, Dict, Any, Tuple

from pydantic import BaseModel
from openai import OpenAI

from .models import (
    Workflow,
    AgentSpec,
    HumanSpec,
    AssignedTask,
    AgenticPlanResponse,
)


logger = logging.getLogger("workflow.agentic")


def _normalize_capability(title: str) -> str:
    s = title.lower()
    for repl in [",", ".", ":", ";", "  "]:
        s = s.replace(repl, " ")
    words = [w for w in s.split() if len(w) > 2]
    if not words:
        return "generic"
    # simple normalization to cluster obvious categories
    if any(k in words for k in ["summarize", "summary", "summarization", "synthesize"]):
        return "summarization"
    if any(k in words for k in ["review", "approve", "approval", "validate", "check"]):
        return "review_approval"
    if any(k in words for k in ["extract", "parse", "analyze", "classify"]):
        return "data_extraction"
    if any(k in words for k in ["generate", "write", "draft", "compose"]):
        return "content_generation"
    if any(k in words for k in ["deploy", "release", "publish"]):
        return "deployment"
    if any(k in words for k in ["test", "qa", "verify"]):
        return "testing"
    if any(k in words for k in ["fetch", "retrieve", "get", "call", "api"]):
        return "api_integration"
    return words[0]


def fallback_agentic_plan(wf: Workflow) -> AgenticPlanResponse:
    """Heuristic grouping when LLM is unavailable.
    - Group agent tasks by a normalized capability derived from title/tool.
    - Group human tasks by whether they look like approvals vs. general reviewers.
    """
    agent_groups: Dict[str, List[str]] = {}
    human_groups: Dict[str, List[str]] = {}

    # Build agent/human groups
    for t in wf.tasks:
        if t.actor == "agent":
            key = t.tool or _normalize_capability(t.title or t.name or t.id)
            agent_groups.setdefault(key, []).append(t.id)
        else:
            key = "manager" if any(k in (t.title or "").lower() for k in ["approve", "approval", "review"]) else "general_human"
            human_groups.setdefault(key, []).append(t.id)

    agents: List[AgentSpec] = []
    humans: List[HumanSpec] = []
    assignments: List[AssignedTask] = []

    # Create specs
    for i, (cap, tids) in enumerate(sorted(agent_groups.items()), start=1):
        agents.append(
            AgentSpec(
                id=f"A{i}",
                name=f"{cap.replace('_', ' ').title()} Agent",
                description=f"Handles {cap.replace('_', ' ')} tasks across the workflow.",
                skills=[cap],
                tools=[],
                parameters_schema=None,
            )
        )
    for j, (role, tids) in enumerate(sorted(human_groups.items()), start=1):
        disp = "Manager" if role == "manager" else "Human Reviewer"
        humans.append(
            HumanSpec(
                id=f"H{j}",
                name=disp,
                description=f"{disp} participating across steps.",
            )
        )

    # Build assignment map: round-robin within the categorized grouping preserving mapping
    agent_key_to_id = {cap: a.id for cap, a in zip(sorted(agent_groups.keys()), agents)}
    human_key_to_id = {role: h.id for role, h in zip(sorted(human_groups.keys()), humans)}

    for t in wf.tasks:
        if t.actor == "agent":
            cap = t.tool or _normalize_capability(t.title or t.name or t.id)
            owner_id = agent_key_to_id.get(cap) or agents[0].id
            instructions = f"Perform: {t.title or t.name}. Use available tools to produce: {', '.join(t.outputs) or 'outputs'}."
            assignments.append(
                AssignedTask(
                    task_id=t.id,
                    owner_type="agent",
                    owner_id=owner_id,
                    instructions=instructions,
                    inputs=t.inputs or [],
                    outputs=t.outputs or [],
                )
            )
        else:
            role = "manager" if any(k in (t.title or "").lower() for k in ["approve", "approval", "review"]) else "general_human"
            owner_id = human_key_to_id.get(role) or humans[0].id
            instructions = f"Review/approve: {t.title or t.name}. Ensure acceptance criteria met."
            assignments.append(
                AssignedTask(
                    task_id=t.id,
                    owner_type="human",
                    owner_id=owner_id,
                    instructions=instructions,
                    inputs=t.inputs or [],
                    outputs=t.outputs or [],
                )
            )

    return AgenticPlanResponse(
        agents=agents,
        humans=humans,
        assignments=assignments,
        engine="heuristic",
        llm_error=None,
        llm_raw=None,
    )


def try_llm_agentic_plan(wf: Workflow) -> Tuple[AgenticPlanResponse | None, str | None, Dict[str, Any] | None]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.info("OPENAI_API_KEY not set; skipping LLM agentic planning")
        return None, None, None

    model = os.getenv("OPENAI_MODEL", "gpt-5")
    reasoning_effort = os.getenv("OPENAI_REASONING_EFFORT", "minimal")

    class ParsedAgentSpec(BaseModel):
        id: str
        name: str
        description: str | None = None
        skills: List[str] = []
        tools: List[str] = []
        parameters_schema: str | None = None  # Changed to string to avoid schema issues
        
        class Config:
            extra = "forbid"

    class ParsedHumanSpec(BaseModel):
        id: str
        name: str
        description: str | None = None
        
        class Config:
            extra = "forbid"

    class ParsedAssignedTask(BaseModel):
        task_id: str
        owner_type: str
        owner_id: str
        instructions: str
        inputs: List[str] = []
        outputs: List[str] = []
        
        class Config:
            extra = "forbid"

    class ParsedAgenticPlan(BaseModel):
        agents: List[ParsedAgentSpec] = []
        humans: List[ParsedHumanSpec] = []
        assignments: List[ParsedAssignedTask] = []
        
        class Config:
            extra = "forbid"

    client = OpenAI(api_key=api_key, base_url=os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1/")

    system = (
        "You are designing an agentic execution plan.\n"
        "- Group similar agent tasks into reusable agents (dedupe).\n"
        "- Group human approval/review to the same human role when appropriate.\n"
        "- For each task, assign owner_id (A# or H#) and write crisp instructions.\n"
        "- Use existing task inputs/outputs; do not invent contradictory artifacts.\n"
        "- Output only valid JSON that matches the provided schema.\n"
    )

    user = (
        "Workflow tasks (JSON):\n" + json.dumps([t.model_dump() for t in wf.tasks], ensure_ascii=False) + "\n\n"
        "Constraints:\n"
        "- Minimize number of agents by capability merging (e.g., summarization -> single agent).\n"
        "- Merge by capability: summarization agent, Email&CalendarAgent, computer use agent, follow up agent,\n"
        "- Human roles should be distinct and not merged unless explicitly stated.\n"
        "- Agent roles should have clear, distinct capabilities, don't create agent with multiple capabilities or roles.\n"
        "- Instructions should be clear, concise, and actionable. There should be one state machine or orchestrator agent which manages the workflow.\n"
        "- Human approvals for legal/contractual/irreversible actions should be explicit.\n"
        "- Assignments must reference existing task_id values.\n"
        "- IDs: agents as A1..An; humans as H1..Hm.\n"
    )

    try:
        logger.info("Calling OpenAI responses.parse for agentic plan (model=%s)", model)
        resp = client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": system + " Strictly output JSON only."},
                {"role": "user", "content": user},
            ],
            text_format=ParsedAgenticPlan,
            reasoning={"effort": reasoning_effort},
            max_output_tokens=120000,
        )
        parsed = getattr(resp, "output_parsed", None)
        if parsed is None:
            raise ValueError("responses.parse returned no parsed agentic plan")

        # Convert to our response model
        agents: List[AgentSpec] = []
        for a in parsed.agents:
            agent_data = a.model_dump()
            # Convert string parameters_schema back to dict if it's a JSON string
            if agent_data.get("parameters_schema") and isinstance(agent_data["parameters_schema"], str):
                try:
                    agent_data["parameters_schema"] = json.loads(agent_data["parameters_schema"])
                except (json.JSONDecodeError, TypeError):
                    agent_data["parameters_schema"] = None
            agents.append(AgentSpec(**agent_data))
        
        humans: List[HumanSpec] = [
            HumanSpec(**h.model_dump()) for h in parsed.humans
        ]
        assignments: List[AssignedTask] = [
            AssignedTask(**asgn.model_dump()) for asgn in parsed.assignments
        ]

        logger.info(
            "LLM agentic planning succeeded (agents=%d, humans=%d, assignments=%d)",
            len(agents), len(humans), len(assignments)
        )
        return (
            AgenticPlanResponse(
                agents=agents,
                humans=humans,
                assignments=assignments,
                engine="responses-parse",
                llm_error=None,
                llm_raw=None,
            ),
            "responses-parse",
            None,
        )
    except Exception as e:
        logger.exception("LLM agentic planning failed: %s", e)
        return None, None, {"llm_error": str(e)}

