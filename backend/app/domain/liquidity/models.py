from pydantic import BaseModel, Field

from app.domain.common.enums import DataHealth


class LiquidityInput(BaseModel):
    resource_id: str = Field(min_length=2, max_length=64)
    balance: float = Field(ge=0)
    safe_buffer: float = Field(ge=0)
    cash_in_5m: float = Field(ge=0)
    cash_out_5m: float = Field(ge=0)
    data_quality_score: float = Field(ge=0, le=1)
    data_health: DataHealth


class LiquidityProjection(BaseModel):
    resource_id: str
    net_burn_per_minute: float = Field(ge=0)
    estimated_runway_minutes: float | None = Field(default=None, ge=0)
    shortage_eta_low_minutes: int | None = Field(default=None, ge=0)
    shortage_eta_high_minutes: int | None = Field(default=None, ge=0)
    shortage_probability_60m: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    evidence: list[str]
