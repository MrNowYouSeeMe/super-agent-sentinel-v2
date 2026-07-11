from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.services.phase6b_runtime import Phase6BPredictionRequest, predict_phase6b
from app.services.phase9_governance import (
    calculate_operational_confidence,
    assess_context,
    analyze_phase9,
    validate_llm_output,
    validate_phase9_input,
)
from app.services.phase9_evidence import build_evidence, match_historical_cases

client = TestClient(app)


def _payload(**updates) -> Phase6BPredictionRequest:
    base = dict(
        episode_id="phase9-test",
        window_id="phase9-window",
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
        language="banglish",
        use_openai_explanation=False,
    )
    base.update(updates)
    return Phase6BPredictionRequest(**base)


def _login(profile_id: str) -> str:
    response = client.post("/api/v1/auth/demo-login", json={"profile_id": profile_id})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_phase9_builds_grounded_analysis() -> None:
    result = analyze_phase9(_payload(), actor_id="test")
    assert result.phase9_version == "phase9-1.0.0"
    assert result.evidence
    assert result.historical_matches
    assert 0 <= result.confidence.final_operational_confidence <= 1
    assert result.llm_input_validation.valid is True
    assert result.human_review_required is True
    assert len(result.audit_event_ids) >= 4
    assert "fraud verdict" in result.safety_boundary.lower()


def test_unreliable_data_activates_safe_fallback() -> None:
    result = analyze_phase9(
        _payload(
            feed_age_seconds=1800,
            data_quality_score=0.35,
            missing_ratio=0.30,
            reconciliation_difference=40_000,
        ),
        actor_id="test",
    )
    assert result.input_validation.safe_mode_required is True
    assert result.safe_fallback_active is True
    assert result.prediction.estimated_time_to_shortage_minutes is None
    assert result.confidence.final_operational_confidence <= 0.55
    assert result.prediction.data_verification_required is True


def test_credential_like_content_is_rejected() -> None:
    report = validate_phase9_input(_payload(episode_id="otp=123456-secret"))
    assert report.valid is False
    assert any(item.code == "PROHIBITED_CREDENTIAL_CONTENT" for item in report.issues)


def test_output_validation_rejects_unsafe_and_unmatched_claims() -> None:
    payload = _payload()
    prediction = predict_phase6b(payload)
    validation = validate_phase9_input(payload)
    context = assess_context(payload)
    matches = match_historical_cases(payload)
    evidence = build_evidence(payload, prediction, matches)
    confidence = calculate_operational_confidence(
        payload,
        prediction,
        validation,
        context,
        evidence,
        matches,
    )
    report = validate_llm_output(
        "Fraud is confirmed. You should freeze the account and contact Nagad immediately.",
        prediction=prediction,
        confidence=confidence,
        evidence=evidence,
    )
    assert report.valid is False
    assert report.issues


def test_phase9_endpoint_auth_and_contract() -> None:
    body = _payload().model_dump(mode="json")
    unauthorized = client.post("/api/v1/ml/phase9/analyze", json=body)
    assert unauthorized.status_code == 401

    token = _login("area-manager-sylhet")
    authorized = client.post(
        "/api/v1/ml/phase9/analyze",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert authorized.status_code == 200, authorized.text
    response = authorized.json()
    assert response["evidence"]
    assert response["confidence"]["final_operational_confidence"] <= 1
    assert response["llm_input_validation"]["valid"] is True


def test_feedback_requires_case_review_and_is_audited() -> None:
    token = _login("area-manager-sylhet")
    analysis = client.post(
        "/api/v1/ml/phase9/analyze",
        json=_payload().model_dump(mode="json"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert analysis.status_code == 200
    body = analysis.json()

    feedback = client.post(
        "/api/v1/ml/phase9/feedback",
        json={
            "analysis_id": body["analysis_id"],
            "area_id": "sylhet",
            "outlet_id": "OUT-1",
            "affected_resource": body["prediction"]["affected_resource"],
            "decision": "needs_more_data",
            "note": "Verify the latest provider feed before closing the case.",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert feedback.status_code == 200, feedback.text
    assert feedback.json()["stored"] is True


def test_phase9_status_endpoint() -> None:
    response = client.get("/api/v1/ml/phase9/status")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["evidence_index_available"] is True
    assert body["evidence_prototype_count"] > 0
