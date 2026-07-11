from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.phase91_audit import verify_audit_chain
from app.services.phase91_case_workflow import create_case, transition_case
from app.services.phase91_guard import (
    Phase91IdempotencyConflict,
    check_rate_limit,
)
from app.services.phase91_models import (
    CaseTransitionRequest,
    Phase91AnalysisRequest,
    ProviderFeedInput,
)
from app.services.phase91_security import (
    contains_cross_provider_reference,
    deterministic_pressure_scores,
)
from app.services.phase91_service import analyze_phase91, redact_phase91_response

client = TestClient(app)


def _payload(**updates) -> Phase91AnalysisRequest:
    values = dict(
        episode_id=f"phase91-test-{uuid4().hex[:8]}",
        window_id=f"phase91-window-{uuid4().hex[:8]}",
        timestamp=datetime.now(timezone.utc),
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
        provider_feeds=[],
        idempotency_key=None,
    )
    values.update(updates)
    return Phase91AnalysisRequest(**values)


def _login(profile_id: str = "area-manager-sylhet") -> str:
    response = client.post("/api/v1/auth/demo-login", json={"profile_id": profile_id})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_phase91_analysis_has_final_hardening_contract() -> None:
    result = analyze_phase91(
        _payload(),
        actor_id=f"test-{uuid4().hex}",
        enforce_rate_limit=False,
    )
    assert result.phase91_version == "phase9.1-1.0.0"
    assert len(result.provider_feeds) == 3
    assert result.provider_attribution.deterministic_scores
    assert result.structured_explanation.evidence_ids
    assert result.structured_validation.valid is True
    assert result.structured_validation.evidence_coverage >= 0.5
    assert result.analysis.human_review_required is True
    assert "No wallet interoperability" in result.safety_boundary


def test_provider_pressure_scores_preserve_separate_resources() -> None:
    scores = deterministic_pressure_scores(_payload())
    assert set(scores) == {"shared_cash", "bkash", "nagad", "rocket"}
    assert all(0 <= value <= 1 for value in scores.values())


def test_bad_provider_feeds_disable_exact_attribution_and_eta() -> None:
    feeds = [
        ProviderFeedInput(
            provider=provider,
            status="conflict",
            feed_age_seconds=60,
            quality_score=0.90,
            reported_balance=100_000,
            reconciled_balance=50_000,
            conflict_amount=50_000,
        )
        for provider in ("bkash", "nagad", "rocket")
    ]
    result = analyze_phase91(
        _payload(provider_feeds=feeds),
        actor_id=f"test-{uuid4().hex}",
        enforce_rate_limit=False,
    )
    if result.provider_attribution.model_resource in {"bkash", "nagad", "rocket"}:
        assert result.provider_attribution.agreement == "insufficient_data"
        assert result.provider_attribution.requires_verification is True
        assert result.analysis.prediction.estimated_time_to_shortage_minutes is None
        assert result.adjusted_operational_confidence <= 0.50


def test_cross_provider_reference_guard() -> None:
    assert not contains_cross_provider_reference(
        "bKash liquidity requires human review.",
        "bkash",
    )
    assert contains_cross_provider_reference(
        "bKash result also exposes Nagad balance.",
        "bkash",
    )



def test_provider_scope_redaction_hides_other_provider_details() -> None:
    result = analyze_phase91(
        _payload(),
        actor_id=f"test-{uuid4().hex}",
        enforce_rate_limit=False,
    )
    model_resource = result.provider_attribution.model_resource
    allowed = (
        {model_resource}
        if model_resource in {"bkash", "nagad", "rocket"}
        else set()
    )
    redacted = redact_phase91_response(result, allowed_providers=allowed)
    assert all(item.provider in allowed for item in redacted.provider_feeds)
    assert all(
        key == "shared_cash" or key in allowed
        for key in redacted.provider_attribution.deterministic_scores
    )
    assert all(
        item.affected_service in allowed
        or item.affected_service in {"shared_cash", "none", "unknown"}
        for item in redacted.analysis.historical_matches
    )

def test_persistent_idempotency_prevents_duplicate_analysis() -> None:
    key = f"idem-{uuid4().hex}"
    payload = _payload(idempotency_key=key)
    actor = f"test-{uuid4().hex}"
    first = analyze_phase91(
        payload,
        actor_id=actor,
        enforce_rate_limit=False,
    )
    second = analyze_phase91(
        payload,
        actor_id=actor,
        enforce_rate_limit=False,
    )
    assert first.analysis.analysis_id == second.analysis.analysis_id
    assert second.idempotent_replay is True


def test_idempotency_key_conflict_is_rejected() -> None:
    key = f"idem-conflict-{uuid4().hex}"
    actor = f"test-{uuid4().hex}"
    first = _payload(idempotency_key=key)
    analyze_phase91(
        first,
        actor_id=actor,
        enforce_rate_limit=False,
    )
    second = first.model_copy(update={"cash_out_amount_5m": 31_000})
    with pytest.raises(Phase91IdempotencyConflict):
        analyze_phase91(
            second,
            actor_id=actor,
            enforce_rate_limit=False,
        )


def test_case_lifecycle_and_hash_chain() -> None:
    analysis = analyze_phase91(
        _payload(),
        actor_id=f"test-{uuid4().hex}",
        enforce_rate_limit=False,
    )
    case = create_case(analysis, actor_id="test-reviewer")
    case = transition_case(
        case.case_id,
        CaseTransitionRequest(action="acknowledge"),
        actor_id="test-reviewer",
    )
    case = transition_case(
        case.case_id,
        CaseTransitionRequest(action="assign", owner_id="area-manager-1"),
        actor_id="test-reviewer",
    )
    case = transition_case(
        case.case_id,
        CaseTransitionRequest(
            action="add_note",
            note="Latest provider feed requested for manual verification.",
        ),
        actor_id="test-reviewer",
    )
    case = transition_case(
        case.case_id,
        CaseTransitionRequest(
            action="escalate",
            target_role="risk_reviewer",
            note="Repeated activity needs evidence review.",
        ),
        actor_id="test-reviewer",
    )
    case = transition_case(
        case.case_id,
        CaseTransitionRequest(
            action="resolve",
            note="Provider feed verified and operational pressure addressed.",
        ),
        actor_id="test-reviewer",
    )
    case = transition_case(
        case.case_id,
        CaseTransitionRequest(action="close"),
        actor_id="test-reviewer",
    )
    assert case.resolution_status == "closed"
    assert case.acknowledgement_status == "acknowledged"
    assert case.owner_id == "area-manager-1"
    assert case.escalation_status == "escalated"
    assert verify_audit_chain().valid is True


def test_rate_limit_enforcement() -> None:
    actor = f"rate-test-{uuid4().hex}"
    for _ in range(30):
        check_rate_limit(actor)
    with pytest.raises(Exception):
        check_rate_limit(actor)


def test_phase91_api_auth_idempotency_and_case_link() -> None:
    body = _payload().model_dump(mode="json")
    unauthorized = client.post("/api/v1/ml/phase91/analyze", json=body)
    assert unauthorized.status_code == 401

    token = _login()
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Idempotency-Key": f"api-idem-{uuid4().hex}",
        "X-Request-ID": f"api-request-{uuid4().hex}",
    }
    response = client.post(
        "/api/v1/ml/phase91/analyze",
        json=body,
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["case"] is not None
    assert payload["structured_validation"]["valid"] is True
    assert payload["request_id"] == headers["X-Request-ID"]

    replay = client.post(
        "/api/v1/ml/phase91/analyze",
        json=body,
        headers=headers,
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["analysis"]["analysis_id"] == payload["analysis"]["analysis_id"]
    assert replay.json()["case"]["case_id"] == payload["case"]["case_id"]


def test_phase91_status_and_audit_endpoints() -> None:
    status_response = client.get("/api/v1/ml/phase91/status")
    assert status_response.status_code == 200
    assert status_response.json()["available"] is True

    token = _login()
    audit_response = client.get(
        "/api/v1/ml/phase91/audit/verify",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert audit_response.status_code == 200
    assert audit_response.json()["valid"] is True
