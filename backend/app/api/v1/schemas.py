from pydantic import BaseModel, Field

from app.domain.common.enums import Language


class ResourceSnapshot(BaseModel):
    resource_id: str = Field(min_length=2, max_length=64)
    balance: float = Field(ge=0)
    safe_buffer: float = Field(ge=0)
    cash_in_5m: float = Field(ge=0)
    cash_out_5m: float = Field(ge=0)
    transaction_count_5m: int = Field(default=0, ge=0)
    repeated_amount_ratio: float = Field(default=0, ge=0, le=1)
    unique_customer_ratio: float = Field(default=1, ge=0, le=1)
    failure_rate: float = Field(default=0, ge=0, le=1)
    feed_age_seconds: int = Field(default=0, ge=0)
    reconciliation_difference: float = Field(default=0, ge=0)
    completeness_ratio: float = Field(default=1, ge=0, le=1)
    source_quality_score: float = Field(default=1, ge=0, le=1)


class IntelligenceRequest(BaseModel):
    outlet_id: str = Field(min_length=2, max_length=64)
    area_id: str = Field(min_length=2, max_length=64)
    language: Language = Language.BANGLISH
    festival_or_market_day: bool = False
    shared_cash: ResourceSnapshot
    providers: list[ResourceSnapshot] = Field(min_length=1, max_length=10)
