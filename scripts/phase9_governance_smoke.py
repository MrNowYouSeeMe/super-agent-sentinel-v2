from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

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

from app.services.phase6b_runtime import Phase6BPredictionRequest
from app.services.phase9_governance import analyze_phase9, phase9_status


def payload(**updates) -> Phase6BPredictionRequest:
    values = dict(
        episode_id="phase9-smoke",
        window_id="phase9-smoke-window",
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
    )
    values.update(updates)
    return Phase6BPredictionRequest(**values)


def main() -> None:
    status = phase9_status()
    if not status.available or not status.evidence_index_available:
        raise RuntimeError("Phase 9 status is unavailable.")

    normal = analyze_phase9(payload(), actor_id="phase9-smoke")
    degraded = analyze_phase9(
        payload(
            episode_id="phase9-degraded",
            feed_age_seconds=1800,
            data_quality_score=0.35,
            missing_ratio=0.30,
            reconciliation_difference=40_000,
        ),
        actor_id="phase9-smoke",
    )

    if not normal.evidence or not normal.historical_matches:
        raise RuntimeError("Phase 9 evidence matching did not return evidence.")
    if degraded.prediction.estimated_time_to_shortage_minutes is not None:
        raise RuntimeError("Degraded-data safe fallback exposed an exact ETA.")
    if not degraded.safe_fallback_active:
        raise RuntimeError("Degraded-data safe fallback was not activated.")

    print("PHASE 9 GOVERNANCE SMOKE PASSED")
    print(f"- version: {normal.phase9_version}")
    print(f"- evidence_items: {len(normal.evidence)}")
    print(f"- historical_matches: {len(normal.historical_matches)}")
    print(
        f"- operational_confidence: "
        f"{normal.confidence.final_operational_confidence:.1%}"
    )
    print(f"- explanation_mode: {normal.explanation_mode}")
    print(
        f"- explanation_evidence_coverage: "
        f"{normal.explanation_validation.evidence_coverage:.1%}"
    )
    print(f"- degraded_safe_fallback: {degraded.safe_fallback_active}")
    print(f"- degraded_eta_hidden: {degraded.prediction.estimated_time_to_shortage_minutes is None}")
    print(f"- audit_events: {len(normal.audit_event_ids)}")


if __name__ == "__main__":
    main()
