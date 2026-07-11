from app.domain.common.enums import Classification, DataHealth, Severity
from app.domain.decision.models import DecisionInput, DecisionResult

SAFE_BOUNDARY = (
    "Decision support only: do not move funds, freeze an account, or treat this "
    "result as a fraud determination."
)


def make_decision(data: DecisionInput) -> DecisionResult:
    risk = max(data.shortage_probability, data.anomaly_score)

    if data.data_health == DataHealth.UNRELIABLE:
        classification = Classification.DATA_QUALITY_ISSUE
        severity = Severity.MEDIUM
        action = "verify_provider_feed_and_reconciliation"
        review = True
    elif data.shortage_probability >= 0.65 and data.anomaly_score >= 0.55:
        classification = Classification.LIQUIDITY_PRESSURE_WITH_UNUSUAL_ACTIVITY
        severity = Severity.HIGH if risk >= 0.80 else Severity.MEDIUM
        action = "assign_area_manager_review"
        review = True
    elif data.shortage_probability >= 0.65:
        classification = Classification.LIQUIDITY_PRESSURE
        severity = Severity.HIGH if data.shortage_probability >= 0.85 else Severity.MEDIUM
        action = "request_operator_verification"
        review = True
    elif data.anomaly_score >= 0.55:
        classification = Classification.UNUSUAL_ACTIVITY
        severity = Severity.MEDIUM
        action = "assign_risk_reviewer"
        review = True
    else:
        classification = Classification.NORMAL_OPERATION
        severity = Severity.LOW
        action = "continue_monitoring"
        review = False

    confidence = round(min(data.data_quality_score, 0.95), 6)
    return DecisionResult(
        classification=classification,
        severity=severity,
        affected_resource=data.resource_id,
        confidence=confidence,
        human_review_required=review,
        recommended_action=action,
        safe_boundary=SAFE_BOUNDARY,
    )
