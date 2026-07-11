from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.services.phase91_models import Phase91Metrics

ROOT = Path(__file__).resolve().parents[3]
REPORT_JSON = ROOT / "reports" / "final" / "PHASE91_FINAL_BACKEND_REPORT.json"


def load_phase91_metrics() -> Phase91Metrics:
    if REPORT_JSON.exists():
        return Phase91Metrics.model_validate_json(
            REPORT_JSON.read_text(encoding="utf-8")
        )
    return Phase91Metrics(
        generated_at=datetime.now(timezone.utc),
        structured_output_validation_rate=0.0,
        degraded_feed_fallback_rate=0.0,
        idempotency_duplicate_prevention_rate=0.0,
        audit_chain_verification_rate=0.0,
        provider_scope_guard_test_rate=0.0,
        model_only_latency_p50_ms=0.0,
        model_only_latency_p95_ms=0.0,
        scenarios_tested=1,
        notes=["Metrics report has not been generated yet."],
    )
