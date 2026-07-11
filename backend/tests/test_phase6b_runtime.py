from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.services.phase6b_runtime import (
    MODEL_PATH,
    Phase6BPredictionRequest,
    _stakeholder_route,
    phase6b_status,
    predict_phase6b,
)

client = TestClient(app)


def _payload() -> Phase6BPredictionRequest:
    return Phase6BPredictionRequest(
        timestamp=datetime(2026, 7, 12, 10, 0, tzinfo=timezone.utc),
        area_id="sylhet",
        outlet_id="OUT-1",
        agent_profile="high_volume",
        location_type="urban",
        provider_mix_shift="bkash_heavy",
        festival_flag=1,
        salary_flag=0,
        remittance_flag=0,
        market_day_flag=1,
        network_recovery_flag=0,
        shared_cash_balance=90_000,
        bkash_balance=7_000,
        nagad_balance=120_000,
        rocket_balance=80_000,
        tx_count_5m=34,
        cash_in_amount_5m=1_000,
        cash_out_amount_5m=30_000,
        net_cash_flow_5m=-29_000,
        velocity_vs_baseline=3.4,
        repeated_amount_ratio=0.74,
        unique_customer_ratio=0.18,
        failure_rate=0.03,
        duplicate_ratio=0.01,
        missing_ratio=0.00,
        out_of_order_ratio=0.00,
        feed_age_seconds=30,
        reconciliation_difference=0,
        data_quality_score=0.96,
        shared_cash_burn_15m=15_000,
        shared_cash_burn_30m=28_000,
        shared_cash_burn_60m=50_000,
        bkash_burn_60m=42_000,
        nagad_burn_60m=5_000,
        rocket_burn_60m=4_000,
        use_openai_explanation=False,
    )


def test_combined_risk_routes_to_area_and_risk() -> None:
    primary, secondary, visibility = _stakeholder_route(
        anomaly=True,
        shortage=True,
        data_issue=False,
        service="bkash",
        high_severity=True,
    )
    assert primary == "area_manager"
    assert secondary == "risk_reviewer"
    assert "bkash_operations" in visibility
    assert "central_operations" in visibility


def test_phase6b_status_matches_artifact_presence() -> None:
    status = phase6b_status()
    assert status.available is MODEL_PATH.exists()
    assert "human reviewer" in status.safety_boundary.lower()


def test_real_phase6b_bundle_predicts_when_present() -> None:
    if not MODEL_PATH.exists():
        return
    result = predict_phase6b(_payload())
    assert 0 <= result.probabilities.anomaly <= 1
    assert (
        result.probabilities.shortage_30m
        <= result.probabilities.shortage_60m
        <= result.probabilities.shortage_120m
    )
    assert result.affected_resource in {"none", "shared_cash", "bkash", "nagad", "rocket"}
    assert "fraud verdict" in result.safety_boundary.lower()


def test_phase6b_status_endpoint() -> None:
    response = client.get("/api/v1/ml/phase6b/status")
    assert response.status_code == 200
    assert "available" in response.json()