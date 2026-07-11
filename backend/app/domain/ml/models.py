from pydantic import BaseModel, Field


class MLFeatureSet(BaseModel):
    resource_id: str
    features: dict[str, float]


class FeatureContribution(BaseModel):
    feature: str
    value: float
    weight: float
    contribution: float
    direction: str


class ModelPrediction(BaseModel):
    resource_id: str
    model_name: str
    model_version: str
    model_mode: str
    anomaly_probability: float = Field(ge=0, le=1)
    shortage_probability_60m: float = Field(ge=0, le=1)
    confidence_adjustment: float = Field(ge=0, le=1)
    notable_signals: list[str]
    anomaly_contributions: list[FeatureContribution]
    shortage_contributions: list[FeatureContribution]

