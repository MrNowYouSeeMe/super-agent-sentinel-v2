from pydantic import BaseModel, Field

from app.domain.common.enums import Classification, DataHealth, Severity


class DecisionInput(BaseModel):
    resource_id: str
    shortage_probability: float = Field(ge=0, le=1)
    anomaly_score: float = Field(ge=0, le=1)
    data_health: DataHealth
    data_quality_score: float = Field(ge=0, le=1)


class DecisionResult(BaseModel):
    classification: Classification
    severity: Severity
    affected_resource: str
    confidence: float = Field(ge=0, le=1)
    human_review_required: bool
    recommended_action: str
    safe_boundary: str
