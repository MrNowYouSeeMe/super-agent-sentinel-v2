from pydantic import BaseModel, Field

from app.domain.common.enums import DataHealth


class DataQualityInput(BaseModel):
    balance: float = Field(ge=0)
    feed_age_seconds: int = Field(ge=0)
    reconciliation_difference: float = Field(ge=0)
    completeness_ratio: float = Field(default=1.0, ge=0, le=1)
    source_quality_score: float = Field(default=1.0, ge=0, le=1)


class DataQualityResult(BaseModel):
    state: DataHealth
    score: float = Field(ge=0, le=1)
    freshness_factor: float = Field(ge=0, le=1)
    reconciliation_factor: float = Field(ge=0, le=1)
    completeness_factor: float = Field(ge=0, le=1)
    evidence: list[str]
