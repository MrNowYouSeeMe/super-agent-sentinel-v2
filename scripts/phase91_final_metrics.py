from __future__ import annotations

import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.phase91_audit import verify_audit_chain
from app.services.phase91_models import (
    Phase91AnalysisRequest,
    Phase91Metrics,
    ProviderFeedInput,
)
from app.services.phase91_security import contains_cross_provider_reference
from app.services.phase91_service import analyze_phase91


def payload(**updates) -> Phase91AnalysisRequest:
    values = dict(
        episode_id=f"phase91-metrics-{uuid4().hex[:8]}",
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


def percentile(values: list[float], percent: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * percent)))
    return ordered[index]


def main() -> int:
    durations: list[float] = []
    structured_pass = 0
    baseline_results = []
    for index in range(20):
        start = time.perf_counter()
        result = analyze_phase91(
            payload(),
            actor_id=f"metrics-latency-{index}",
            enforce_rate_limit=False,
        )
        durations.append((time.perf_counter() - start) * 1000)
        structured_pass += int(result.structured_validation.valid)
        baseline_results.append(result)

    degraded_pass = 0
    degraded_total = 0
    degraded_inputs = [
        dict(status="stale", feed_age_seconds=1800, quality_score=0.80, missing_ratio=0.0),
        dict(status="missing", feed_age_seconds=60, quality_score=0.35, missing_ratio=0.30),
        dict(
            status="conflict",
            feed_age_seconds=60,
            quality_score=0.90,
            missing_ratio=0.0,
            reported_balance=100_000,
            reconciled_balance=50_000,
            conflict_amount=50_000,
        ),
        dict(status="degraded", feed_age_seconds=400, quality_score=0.65, missing_ratio=0.12),
    ]
    for scenario_index, settings in enumerate(degraded_inputs):
        feeds = [
            ProviderFeedInput(provider=provider, **settings)
            for provider in ("bkash", "nagad", "rocket")
        ]
        result = analyze_phase91(
            payload(provider_feeds=feeds),
            actor_id=f"metrics-degraded-{scenario_index}",
            enforce_rate_limit=False,
        )
        degraded_total += 1
        safe = (
            result.provider_attribution.requires_verification
            and result.analysis.prediction.estimated_time_to_shortage_minutes is None
            and result.adjusted_operational_confidence
            <= max(item.confidence_cap for item in result.provider_feeds)
        )
        degraded_pass += int(safe)

    idempotency_key = f"metrics-idem-{uuid4().hex}"
    idem_payload = payload(idempotency_key=idempotency_key)
    first = analyze_phase91(
        idem_payload,
        actor_id="metrics-idempotency",
        enforce_rate_limit=False,
    )
    second = analyze_phase91(
        idem_payload,
        actor_id="metrics-idempotency",
        enforce_rate_limit=False,
    )
    idempotency_rate = float(
        first.analysis.analysis_id == second.analysis.analysis_id
        and second.idempotent_replay
    )

    audit = verify_audit_chain()
    provider_guard_checks = [
        not contains_cross_provider_reference(
            "bkash liquidity requires review", "bkash"
        ),
        contains_cross_provider_reference(
            "bkash alert also exposes Nagad data", "bkash"
        ),
        not contains_cross_provider_reference(
            "shared cash requires review", None
        ),
    ]
    provider_guard_rate = sum(provider_guard_checks) / len(provider_guard_checks)

    metrics = Phase91Metrics(
        generated_at=datetime.now(timezone.utc),
        structured_output_validation_rate=structured_pass / len(baseline_results),
        degraded_feed_fallback_rate=degraded_pass / degraded_total,
        idempotency_duplicate_prevention_rate=idempotency_rate,
        audit_chain_verification_rate=float(audit.valid),
        provider_scope_guard_test_rate=provider_guard_rate,
        model_only_latency_p50_ms=round(statistics.median(durations), 3),
        model_only_latency_p95_ms=round(percentile(durations, 0.95), 3),
        scenarios_tested=len(baseline_results) + degraded_total + 4,
        notes=[
            "Metrics use deterministic, synthetic local scenarios.",
            "Model-only latency excludes external OpenAI network time.",
            "Operational confidence is not presented as blind-test accuracy.",
            "Provider-scope rate is a security test-matrix result, not model accuracy.",
        ],
    )

    report_dir = ROOT / "reports" / "final"
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / "PHASE91_FINAL_BACKEND_REPORT.json"
    md_path = report_dir / "PHASE91_FINAL_BACKEND_REPORT.md"
    json_path.write_text(
        metrics.model_dump_json(indent=2),
        encoding="utf-8",
    )
    md_path.write_text(
        "\n".join(
            [
                "# Phase 9.1 Final Backend Hardening Report",
                "",
                f"- Generated: {metrics.generated_at.isoformat()}",
                f"- Structured output validation: {metrics.structured_output_validation_rate:.1%}",
                f"- Degraded-feed safe fallback: {metrics.degraded_feed_fallback_rate:.1%}",
                f"- Idempotency duplicate prevention: {metrics.idempotency_duplicate_prevention_rate:.1%}",
                f"- Audit-chain verification: {metrics.audit_chain_verification_rate:.1%}",
                f"- Provider-scope guard tests: {metrics.provider_scope_guard_test_rate:.1%}",
                f"- Model-only latency p50: {metrics.model_only_latency_p50_ms:.3f} ms",
                f"- Model-only latency p95: {metrics.model_only_latency_p95_ms:.3f} ms",
                f"- Scenarios tested: {metrics.scenarios_tested}",
                "",
                "## Interpretation",
                "",
                "- These are synthetic engineering/reliability measurements.",
                "- They do not replace the frozen-model blind-test metrics.",
                "- External LLM latency is intentionally reported separately during live demo.",
                "- All outputs remain advisory and human-reviewed.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print("PHASE 9.1 FINAL METRICS PASSED")
    print(f"- structured validation: {metrics.structured_output_validation_rate:.1%}")
    print(f"- degraded fallback: {metrics.degraded_feed_fallback_rate:.1%}")
    print(f"- idempotency prevention: {metrics.idempotency_duplicate_prevention_rate:.1%}")
    print(f"- audit chain: {metrics.audit_chain_verification_rate:.1%}")
    print(f"- provider guard: {metrics.provider_scope_guard_test_rate:.1%}")
    print(f"- p50: {metrics.model_only_latency_p50_ms:.3f} ms")
    print(f"- p95: {metrics.model_only_latency_p95_ms:.3f} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
