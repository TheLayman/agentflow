from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


Granularity = Literal["low", "medium", "high"]


class Task(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    description: Optional[str] = None
    depends_on: List[str] = Field(default_factory=list)
    role: Optional[str] = None
    inputs: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    estimate: Optional[str] = None
    acceptance_criteria: Optional[str] = None
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
