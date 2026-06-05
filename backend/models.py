from __future__ import annotations

from pydantic import BaseModel, Field


class KnowledgeDocument(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    content: str = Field(min_length=20)
    tags: list[str] = Field(default_factory=list)


class RunRequest(BaseModel):
    goal: str = Field(min_length=4, max_length=500)
    persona: str = "product_manager"
    top_k: int = Field(default=5, ge=1, le=8)
    temperature: float = Field(default=0.35, ge=0, le=1)
    strict_grounding: bool = True
    risk_mode: str = "balanced"


class Source(BaseModel):
    title: str
    chunk_id: str
    score: float
    snippet: str
    tags: list[str]


class AgentStep(BaseModel):
    role: str
    title: str
    detail: str
    status: str


class GuardrailFinding(BaseModel):
    level: str
    title: str
    detail: str


class Evaluation(BaseModel):
    groundedness: int
    relevance: int
    coverage: int
    risk: int


class RunResponse(BaseModel):
    answer: str
    action_plan: list[str]
    sources: list[Source]
    agents: list[AgentStep]
    guardrails: list[GuardrailFinding]
    evaluation: Evaluation
    metrics: dict[str, float | int | str]
