from __future__ import annotations

from typing import List, Literal, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict


Granularity = Literal["low", "medium", "high"]


class Task(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str  # Format: "T\d+"
    title: str  # One clear verb
    actor: Literal["agent", "human"]
    depends_on: List[str] = Field(default_factory=list)  # ids only
    inputs: List[str] = Field(default_factory=list)  # explicit artifacts/fields
    outputs: List[str] = Field(default_factory=list)  # explicit artifacts/fields
    tool: Optional[str] = None  # required when actor="agent"
    parameters: Optional[str] = None  # JSON string for agent call parameters to avoid OpenAI schema issues
    approval: Literal["none", "human", "auto"] = "none"
    acceptance_criteria: List[str] = Field(default_factory=list)  # objective checks
    parallelizable: bool = False
    
    # Legacy fields for backward compatibility (marked as deprecated)
    name: Optional[str] = None  # Use title instead
    description: Optional[str] = None
    role: Optional[str] = None  # Use actor instead
    tools: List[str] = Field(default_factory=list)  # Use tool instead
    estimate: Optional[str] = None
    risk: Optional[str] = None
    notes: Optional[str] = None


class Workflow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    tasks: List[Task]
    edges: List[tuple[str, str]] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    version: str = "0.1"


class DecomposeRequest(BaseModel):
    text: str
    title: Optional[str] = None
    granularity: Granularity = "medium"


class DecomposeResponse(BaseModel):
    workflow: Workflow
    mermaid: str
    topo_order: List[str] = Field(default_factory=list)
    issues: List[str] = Field(default_factory=list)
    engine: str | None = None
    llm_error: str | None = None
    llm_raw: str | None = None


# ---------------- Agentic Planning Models ----------------

class AgentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str  # Format: "A\d+"
    name: str
    description: str | None = None
    skills: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    parameters_schema: Dict[str, Any] | None = None


class HumanSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str  # Format: "H\d+"
    name: str
    description: str | None = None


class AssignedTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str
    owner_type: Literal["agent", "human"]
    owner_id: str  # e.g., A1 or H1
    instructions: str
    inputs: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)


class AgenticPlanRequest(BaseModel):
    workflow: Workflow


class AgenticPlanResponse(BaseModel):
    agents: List[AgentSpec] = Field(default_factory=list)
    humans: List[HumanSpec] = Field(default_factory=list)
    assignments: List[AssignedTask] = Field(default_factory=list)
    engine: str | None = None
    llm_error: str | None = None
    llm_raw: str | None = None
