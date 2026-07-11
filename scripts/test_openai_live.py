from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

for key, value in dotenv_values(ROOT / ".env").items():
    if value is not None:
        os.environ[str(key)] = str(value)

from app.core.config import get_settings

clear = getattr(get_settings, "cache_clear", None)
if callable(clear):
    clear()

from app.services.phase91_models import Phase91AnalysisRequest
from app.services.phase91_service import analyze_phase91


def _enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _payload() -> Phase91AnalysisRequest:
    return Phase91AnalysisRequest(
        episode_id=f"safe-openai-live-{uuid4().hex[:8]}",
        window_id=f"safe-openai-window-{uuid4().hex[:8]}",
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


def main() -> int:
    api_key = os.getenv("OPENAI_API_KEY", "")
    openai_enabled = _enabled(os.getenv("OPENAI_ENABLED"))

    source_text = Path(__file__).read_text(encoding="utf-8")
    if api_key and api_key in source_text:
        raise RuntimeError("Secret safety check failed: API key is hardcoded in this file.")

    if not openai_enabled or not api_key:
        print("OPENAI LIVE TEST SKIPPED")
        print("- reason: OPENAI_ENABLED is not true or OPENAI_API_KEY is not configured in root .env")
        print("- safe_script: no hardcoded API key")
        return 0

    result = analyze_phase91(
        _payload(),
        actor_id="safe-openai-live-test",
        request_id=f"safe-openai-{uuid4().hex[:12]}",
        enforce_rate_limit=False,
    )

    mode = result.analysis.explanation_mode
    if mode not in {"openai", "openai_validated"}:
        raise RuntimeError(f"OpenAI was configured but explanation_mode was {mode!r}.")

    if not result.structured_validation.valid:
        raise RuntimeError("Structured explanation validation failed.")

    print("SAFE OPENAI LIVE TEST PASSED")
    print(f"- explanation_mode: {mode}")
    print(f"- phase91_version: {result.phase91_version}")
    print(f"- evidence_coverage: {result.structured_validation.evidence_coverage:.1%}")
    print("- key_source: root .env / environment only")
    print("- hardcoded_key: NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
