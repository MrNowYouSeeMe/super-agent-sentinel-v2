from pydantic import BaseModel, Field

from app.api.v1.schemas import IntelligenceRequest, ResourceSnapshot
from app.domain.anomaly.models import AnomalyInput, AnomalyResult
from app.domain.anomaly.service import evaluate_anomaly
from app.domain.common.enums import DataHealth
from app.domain.data_quality.models import DataQualityInput, DataQualityResult
from app.domain.data_quality.service import evaluate_data_quality
from app.domain.decision.models import DecisionInput, DecisionResult
from app.domain.decision.service import make_decision
from app.domain.liquidity.models import LiquidityInput, LiquidityProjection
from app.domain.liquidity.service import project_liquidity
from app.domain.ml.features import build_resource_features
from app.domain.ml.models import ModelPrediction
from app.services.explanations import deterministic_explanation
from app.services.ml_runtime import predict_resource


class ResourceAnalysis(BaseModel):
    resource_id: str
    data_quality: DataQualityResult
    liquidity: LiquidityProjection
    anomaly: AnomalyResult
    ml_prediction: ModelPrediction
    fused_shortage_probability_60m: float = Field(ge=0, le=1)
    fused_anomaly_score: float = Field(ge=0, le=1)
    fused_confidence: float = Field(ge=0, le=1)


class IntelligenceResponse(BaseModel):
    outlet_id: str
    area_id: str
    resources: list[ResourceAnalysis]
    decision: DecisionResult
    evidence: list[str]
    possible_normal_context: list[str]
    explanation: str


def _fuse_scores(
    *,
    rule_shortage: float,
    model_shortage: float,
    rule_anomaly: float,
    model_anomaly: float,
    data_quality_score: float,
    data_health: DataHealth,
) -> tuple[float, float, float]:
    shortage = 0.70 * rule_shortage + 0.30 * model_shortage
    anomaly = 0.65 * rule_anomaly + 0.35 * model_anomaly
    confidence = min(0.95, data_quality_score)
    if data_health == DataHealth.DEGRADED:
        confidence = min(confidence, 0.70)
    if data_health == DataHealth.UNRELIABLE:
        confidence = min(confidence, 0.40)
    return round(shortage, 6), round(anomaly, 6), round(confidence, 6)


def _analyze_resource(
    resource: ResourceSnapshot,
    *,
    festival_or_market_day: bool,
) -> ResourceAnalysis:
    quality = evaluate_data_quality(
        DataQualityInput(
            balance=resource.balance,
            feed_age_seconds=resource.feed_age_seconds,
            reconciliation_difference=resource.reconciliation_difference,
            completeness_ratio=resource.completeness_ratio,
            source_quality_score=resource.source_quality_score,
        )
    )
    liquidity = project_liquidity(
        LiquidityInput(
            resource_id=resource.resource_id,
            balance=resource.balance,
            safe_buffer=resource.safe_buffer,
            cash_in_5m=resource.cash_in_5m,
            cash_out_5m=resource.cash_out_5m,
            data_quality_score=quality.score,
            data_health=quality.state,
        )
    )
    anomaly = evaluate_anomaly(
        AnomalyInput(
            transaction_count_5m=resource.transaction_count_5m,
            cash_in_5m=resource.cash_in_5m,
            cash_out_5m=resource.cash_out_5m,
            repeated_amount_ratio=resource.repeated_amount_ratio,
            unique_customer_ratio=resource.unique_customer_ratio,
            failure_rate=resource.failure_rate,
            festival_or_market_day=festival_or_market_day,
        )
    )
    ml_prediction = predict_resource(
        build_resource_features(
            resource,
            data_quality=quality,
            liquidity=liquidity,
            festival_or_market_day=festival_or_market_day,
        )
    )
    fused_shortage, fused_anomaly, fused_confidence = _fuse_scores(
        rule_shortage=liquidity.shortage_probability_60m,
        model_shortage=ml_prediction.shortage_probability_60m,
        rule_anomaly=anomaly.score,
        model_anomaly=ml_prediction.anomaly_probability,
        data_quality_score=quality.score,
        data_health=quality.state,
    )
    return ResourceAnalysis(
        resource_id=resource.resource_id,
        data_quality=quality,
        liquidity=liquidity,
        anomaly=anomaly,
        ml_prediction=ml_prediction,
        fused_shortage_probability_60m=fused_shortage,
        fused_anomaly_score=fused_anomaly,
        fused_confidence=fused_confidence,
    )


def analyze(request: IntelligenceRequest) -> IntelligenceResponse:
    resources = [
        _analyze_resource(
            request.shared_cash,
            festival_or_market_day=request.festival_or_market_day,
        )
    ]
    resources.extend(
        _analyze_resource(
            provider,
            festival_or_market_day=request.festival_or_market_day,
        )
        for provider in request.providers
    )

    selected = max(
        resources,
        key=lambda item: max(
            item.fused_shortage_probability_60m,
            item.fused_anomaly_score,
            1.0 if item.data_quality.state == DataHealth.UNRELIABLE else 0.0,
        ),
    )
    decision = make_decision(
        DecisionInput(
            resource_id=selected.resource_id,
            shortage_probability=selected.fused_shortage_probability_60m,
            anomaly_score=selected.fused_anomaly_score,
            data_health=selected.data_quality.state,
            data_quality_score=selected.fused_confidence,
        )
    )

    evidence = [
        *selected.data_quality.evidence,
        *selected.liquidity.evidence,
        *selected.anomaly.evidence,
        *selected.ml_prediction.notable_signals,
    ]
    explanation = deterministic_explanation(
        request.language, decision, selected.liquidity
    )
    return IntelligenceResponse(
        outlet_id=request.outlet_id,
        area_id=request.area_id,
        resources=resources,
        decision=decision,
        evidence=evidence,
        possible_normal_context=selected.anomaly.possible_normal_context,
        explanation=explanation,
    )

