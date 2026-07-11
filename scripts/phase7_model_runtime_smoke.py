from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.phase6b_runtime import Phase6BPredictionRequest, phase6b_status, predict_phase6b


def main() -> None:
    status = phase6b_status()
    if not status.available:
        raise RuntimeError(f"Phase 6B model is unavailable: {status.model_path}")

    result = predict_phase6b(
        Phase6BPredictionRequest(
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
            use_openai_explanation=False,
        )
    )

    print("PHASE 7 MODEL RUNTIME SMOKE PASSED")
    print(f"- model_version: {result.model_version}")
    print(f"- classification: {result.classification}")
    print(f"- affected_resource: {result.affected_resource}")
    print(f"- anomaly_probability: {result.probabilities.anomaly:.4f}")
    print(f"- shortage_probability_60m: {result.probabilities.shortage_60m:.4f}")
    print(f"- primary_stakeholder: {result.primary_stakeholder}")
    print(f"- secondary_stakeholder: {result.secondary_stakeholder}")
    print(f"- human_review_required: {result.human_review_required}")
    print(f"- explanation_mode: {result.explanation_mode}")


if __name__ == "__main__":
    main()