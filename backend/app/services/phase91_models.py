from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.services.phase6b_runtime import Phase6BPredictionRequest
from app.services.phase9_governance import Phase9AnalysisResponse

ProviderName = Literal["bkash", "nagad", "rocket"]
FeedStatus = Literal["healthy", "stale", "missing", "conflict", "degraded"]


class ProviderFeedInput(BaseModel):
    provider: ProviderName
    status: FeedStatus = "healthy"
    feed_age_seconds: float = Field(default=0, ge=0, le=86_400)
    quality_score: float = Field(default=1.0, ge=0, le=1)
    missing_ratio: float = Field(default=0.0, ge=0, le=1)
    reported_balance: float | None = Field(default=None, ge=0)
    reconciled_balance: float | None = Field(default=None, ge=0)
    conflict_amount: float = Field(default=0.0, ge=0)


class Phase91AnalysisRequest(Phase6BPredictionRequest):
    provider_feeds: list[ProviderFeedInput] = Field(default_factory=list)
    idempotency_key: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )

    @field_validator("provider_feeds")
    @classmethod
    def unique_providers(cls, value: list[ProviderFeedInput]) -> list[ProviderFeedInput]:
        providers = [item.provider for item in value]
        if len(providers) != len(set(providers)):
            raise ValueError("Each provider may appear only once in provider_feeds.")
        return value


class ProviderFeedAssessment(BaseModel):
    provider: ProviderName
    status: FeedStatus
    supported_for_decision: bool
    confidence_cap: float = Field(ge=0, le=1)
    reasons: list[str]
    feed_age_seconds: float = Field(ge=0)
    quality_score: float = Field(ge=0, le=1)
    missing_ratio: float = Field(ge=0, le=1)
    conflict_amount: float = Field(ge=0)


class ProviderAttribution(BaseModel):
    model_resource: str
    deterministic_resource: str
    effective_resource: str
    agreement: Literal["confirmed", "close", "disagreement", "insufficient_data"]
    deterministic_scores: dict[str, float]
    confidence_adjustment: float = Field(ge=-0.35, le=0.15)
    requires_verification: bool
    reasons: list[str]


class StructuredExplanation(BaseModel):
    situation: str
    evidence_ids: list[str]
    uncertainty: str
    normal_alternative: str | None
    safe_next_step: str
    human_review_required: bool = True
    disclaimer: str
    narrative: str
    language: Literal["english", "bangla", "banglish"]


class StructuredValidation(BaseModel):
    valid: bool
    evidence_coverage: float = Field(ge=0, le=1)
    issues: list[str]
    fallback_used: bool


class CaseNote(BaseModel):
    note_id: str
    actor_id: str
    text: str
    created_at: datetime


class CaseEscalation(BaseModel):
    escalation_id: str
    actor_id: str
    target_role: str
    reason: str
    created_at: datetime


class CoordinationCase(BaseModel):
    case_id: str
    analysis_id: str
    provider_id: str | None
    area_id: str
    outlet_id: str
    severity: str
    recipient_role: str
    owner_id: str | None
    acknowledgement_status: Literal["awaiting", "acknowledged"]
    acknowledged_at: datetime | None
    escalation_status: Literal["not_escalated", "escalated"]
    resolution_status: Literal["open", "under_review", "resolved", "closed"]
    recommended_action: str
    notes: list[CaseNote]
    escalations: list[CaseEscalation]
    created_at: datetime
    updated_at: datetime


class CaseTransitionRequest(BaseModel):
    action: Literal["acknowledge", "assign", "add_note", "escalate", "resolve", "close"]
    owner_id: str | None = Field(default=None, min_length=2, max_length=120)
    note: str | None = Field(default=None, min_length=3, max_length=500)
    target_role: str | None = Field(default=None, min_length=2, max_length=120)

    @field_validator("owner_id", "note", "target_role")
    @classmethod
    def reject_secret_like_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        lowered = clean.lower()
        forbidden = ("password", "otp", "pin=", "api_key", "private_key", "sk-proj-", "sk-")
        if any(token in lowered for token in forbidden):
            raise ValueError("Credentials or secrets are not allowed in case actions.")
        return clean


class AuditVerification(BaseModel):
    valid: bool
    event_count: int
    broken_index: int | None
    latest_hash: str | None
    message: str


class Phase91AnalysisResponse(BaseModel):
    phase91_version: str
    request_id: str
    area_id: str
    outlet_id: str
    language: Literal["english", "bangla", "banglish"]
    analysis: Phase9AnalysisResponse
    provider_feeds: list[ProviderFeedAssessment]
    provider_attribution: ProviderAttribution
    adjusted_operational_confidence: float = Field(ge=0, le=1)
    structured_explanation: StructuredExplanation
    structured_validation: StructuredValidation
    case: CoordinationCase | None
    idempotent_replay: bool
    safety_boundary: str


class Phase91Status(BaseModel):
    available: bool
    phase91_version: str
    capabilities: list[str]
    safety_boundary: str


class Phase91Metrics(BaseModel):
    generated_at: datetime
    structured_output_validation_rate: float = Field(ge=0, le=1)
    degraded_feed_fallback_rate: float = Field(ge=0, le=1)
    idempotency_duplicate_prevention_rate: float = Field(ge=0, le=1)
    audit_chain_verification_rate: float = Field(ge=0, le=1)
    provider_scope_guard_test_rate: float = Field(ge=0, le=1)
    model_only_latency_p50_ms: float = Field(ge=0)
    model_only_latency_p95_ms: float = Field(ge=0)
    scenarios_tested: int = Field(ge=1)
    notes: list[str]
