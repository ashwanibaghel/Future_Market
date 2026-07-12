from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


MISSION_CONTROL_VERSION = "mission-control-v1.0"


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class LifecycleState(str, Enum):
    DETECTED = "DETECTED"
    VERIFIED = "VERIFIED"
    EVIDENCE_CREATED = "EVIDENCE_CREATED"
    RECOMMENDATION_GENERATED = "RECOMMENDATION_GENERATED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    REPLAY_VALIDATION = "REPLAY_VALIDATION"
    APPROVED = "APPROVED"
    IMPLEMENTED = "IMPLEMENTED"
    MONITORED = "MONITORED"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class EvidenceItem(BaseModel):
    id: str
    module: str
    severity: Severity
    finding: str
    metric: str
    value: float | int | str | None = None
    target: float | int | str | None = None
    supporting_data: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    affected_modules: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    version: str = MISSION_CONTROL_VERSION


class Recommendation(BaseModel):
    id: str
    title: str
    module: str
    status: str = "PENDING_HUMAN_APPROVAL"
    confidence: float
    supporting_evidence: list[str] = Field(default_factory=list)
    supporting_metrics: dict[str, Any] = Field(default_factory=dict)
    expected_impact: dict[str, float] = Field(default_factory=dict)
    risks: list[str] = Field(default_factory=list)
    affected_modules: list[str] = Field(default_factory=list)
    lifecycle_state: LifecycleState = LifecycleState.RECOMMENDATION_GENERATED
    created_at: datetime = Field(default_factory=datetime.utcnow)
    version: str = MISSION_CONTROL_VERSION


class ConstitutionCheck(BaseModel):
    key: str
    rule: str
    status: str
    severity: Severity
    reason: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class ScoreComponent(BaseModel):
    key: str
    label: str
    value: float
    weight: float
    weighted_value: float
    target: float
    status: str


class ScoreCard(BaseModel):
    name: str
    score: float
    status: str
    formula_version: str = "score-formulas-v1"
    components: list[ScoreComponent]


class RoadmapPhase(BaseModel):
    phase: str
    title: str
    completion_pct: float
    completed_tasks: int
    total_tasks: int
    status: str
    modules: list[str]

