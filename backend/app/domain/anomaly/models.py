from pydantic import BaseModel, Field


class AnomalyInput(BaseModel):
    transaction_count_5m: int = Field(ge=0)
    cash_in_5m: float = Field(ge=0)
    cash_out_5m: float = Field(ge=0)
    repeated_amount_ratio: float = Field(ge=0, le=1)
    unique_customer_ratio: float = Field(ge=0, le=1)
    failure_rate: float = Field(ge=0, le=1)
    festival_or_market_day: bool = False


class AnomalyResult(BaseModel):
    score: float = Field(ge=0, le=1)
    evidence: list[str]
    possible_normal_context: list[str]
