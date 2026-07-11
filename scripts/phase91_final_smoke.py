from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import dotenv_values

for key, value in dotenv_values(ROOT / ".env").items():
    if value is not None:
        os.environ[str(key)] = str(value)

from app.core.config import get_settings

clear = getattr(get_settings, "cache_clear", None)
if callable(clear):
    clear()

from app.services.phase91_audit import verify_audit_chain
from app.services.phase91_case_workflow import create_case, transition_case
from app.services.phase91_models import (
    CaseTransitionRequest,
    Phase91AnalysisRequest,
    ProviderFeedInput,
)
from app.services.phase91_service import analyze_phase91, attach_case, phase91_status


def payload(**updates) -> Phase91AnalysisRequest:
    values = dict(
        episode_id=f"phase91-smoke-{uuid4().hex[:8]}",
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
        use_openai_explanation=True,
        provider_feeds=[],
        idempotency_key=None,
    )
    values.update(updates)
    return Phase91AnalysisRequest(**values)


def main() -> None:
    status = phase91_status()
    if not status.available:
        raise RuntimeError("Phase 9.1 status is unavailable.")

    actor = "phase91-smoke"
    key = f"phase91-smoke-idem-{uuid4().hex}"
    normal_payload = payload(idempotency_key=key)
    normal = analyze_phase91(
        normal_payload,
        actor_id=actor,
        request_id="phase91-smoke-request",
        enforce_rate_limit=False,
    )
    replay = analyze_phase91(
        normal_payload,
        actor_id=actor,
        request_id="phase91-smoke-request",
        enforce_rate_limit=False,
    )
    if normal.analysis.analysis_id != replay.analysis.analysis_id:
        raise RuntimeError("Idempotency did not preserve the analysis ID.")
    if not replay.idempotent_replay:
        raise RuntimeError("Idempotent replay was not marked.")

    conflict_feeds = [
        ProviderFeedInput(
            provider=provider,
            status="conflict",
            feed_age_seconds=60,
            quality_score=0.90,
            reported_balance=100_000,
            reconciled_balance=40_000,
            conflict_amount=60_000,
        )
        for provider in ("bkash", "nagad", "rocket")
    ]
    degraded = analyze_phase91(
        payload(
            episode_id="phase91-conflict-smoke",
            provider_feeds=conflict_feeds,
            use_openai_explanation=False,
        ),
        actor_id="phase91-degraded-smoke",
        enforce_rate_limit=False,
    )
    if degraded.provider_attribution.model_resource in {"bkash", "nagad", "rocket"}:
        if not degraded.provider_attribution.requires_verification:
            raise RuntimeError("Conflicting provider feeds did not require verification.")
        if degraded.analysis.prediction.estimated_time_to_shortage_minutes is not None:
            raise RuntimeError("Conflicting provider feeds exposed an exact ETA.")

    case = create_case(normal, actor_id=actor)
    case = transition_case(
        case.case_id,
        CaseTransitionRequest(action="acknowledge"),
        actor_id=actor,
    )
    case = transition_case(
        case.case_id,
        CaseTransitionRequest(action="assign", owner_id="area-manager-sylhet"),
        actor_id=actor,
    )
    case = transition_case(
        case.case_id,
        CaseTransitionRequest(
            action="add_note",
            note="Latest provider feed requested and evidence reviewed.",
        ),
        actor_id=actor,
    )
    case = transition_case(
        case.case_id,
        CaseTransitionRequest(
            action="escalate",
            target_role="risk_reviewer",
            note="Unusual pattern requires independent human review.",
        ),
        actor_id=actor,
    )
    case = transition_case(
        case.case_id,
        CaseTransitionRequest(
            action="resolve",
            note="Feed verified and operational response completed.",
        ),
        actor_id=actor,
    )
    case = transition_case(
        case.case_id,
        CaseTransitionRequest(action="close"),
        actor_id=actor,
    )
    final = attach_case(normal, case)
    audit = verify_audit_chain()

    if not final.structured_validation.valid:
        raise RuntimeError("Structured explanation validation failed.")
    if final.structured_validation.evidence_coverage < 0.50:
        raise RuntimeError("Structured explanation evidence coverage is too low.")
    if final.case is None or final.case.resolution_status != "closed":
        raise RuntimeError("Complete case lifecycle failed.")
    if not audit.valid:
        raise RuntimeError("Tamper-evident audit chain verification failed.")

    print("PHASE 9.1 FINAL HARDENING SMOKE PASSED")
    print(f"- version: {final.phase91_version}")
    print(f"- model_resource: {final.provider_attribution.model_resource}")
    print(f"- deterministic_resource: {final.provider_attribution.deterministic_resource}")
    print(f"- attribution_agreement: {final.provider_attribution.agreement}")
    print(f"- adjusted_confidence: {final.adjusted_operational_confidence:.1%}")
    print(f"- structured_output_valid: {final.structured_validation.valid}")
    print(f"- evidence_coverage: {final.structured_validation.evidence_coverage:.1%}")
    print(f"- phase9_explanation_mode: {final.analysis.explanation_mode}")
    print(f"- idempotency_replay: {replay.idempotent_replay}")
    print(f"- case_status: {final.case.resolution_status}")
    print(f"- audit_chain_valid: {audit.valid}")
    print(f"- audit_events: {audit.event_count}")


if __name__ == "__main__":
    main()
