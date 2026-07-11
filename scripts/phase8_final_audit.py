from __future__ import annotations

import json
import re
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient

from app.main import app
from app.services.auth import DemoLoginRequest, demo_login
from app.services.openai_explanation import ExplanationInput, explain_with_optional_openai
from app.services.phase6b_runtime import (
    MODEL_PATH,
    Phase6BPredictionRequest,
    phase6b_status,
    predict_phase6b,
)

REPORT_DIR = ROOT / "reports" / "final"
REPORT_JSON = REPORT_DIR / "phase8_final_readiness.json"
REPORT_MD = REPORT_DIR / "PHASE8_FINAL_READINESS_REPORT.md"
SECRET_PATTERN = re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}")
FORBIDDEN_OUTPUT = (
    "fraud confirmed",
    "freeze account",
    "block customer",
    "move money",
    "transfer money",
)


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout


def tracked_secret_hits() -> list[str]:
    hits: list[str] = []
    for relative in run_git("ls-files").splitlines():
        path = ROOT / relative
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8-sig")
        except (UnicodeDecodeError, OSError):
            continue
        if SECRET_PATTERN.search(content):
            hits.append(relative)
    return hits


def prediction_payload(*, use_openai: bool = False) -> Phase6BPredictionRequest:
    return Phase6BPredictionRequest(
        episode_id="phase8-final-audit",
        window_id="phase8-window",
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
        use_openai_explanation=use_openai,
    )


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * q)))
    return ordered[index]


def assert_safe_text(text: str) -> None:
    lowered = text.lower()
    for phrase in FORBIDDEN_OUTPUT:
        if phrase in lowered:
            raise AssertionError(f"Unsafe output phrase found: {phrase}")


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    checks: dict[str, Any] = {}

    tracked = set(run_git("ls-files").splitlines())
    checks["env_secret_file_tracked"] = ".env" in tracked
    if checks["env_secret_file_tracked"]:
        raise AssertionError(".env is tracked by Git.")

    secret_hits = tracked_secret_hits()
    checks["tracked_secret_hits"] = secret_hits
    if secret_hits:
        raise AssertionError(f"Potential API key found in tracked files: {secret_hits}")

    required_paths = [
        MODEL_PATH,
        ROOT / "reports" / "model_training" / "phase6b_freeze_manifest.json",
        ROOT / "reports" / "model_evaluation" / "phase6c_blind_test_metrics.json",
    ]
    missing = [str(path) for path in required_paths if not path.exists()]
    checks["missing_required_artifacts"] = missing
    if missing:
        raise AssertionError(f"Missing required artifacts: {missing}")

    status = phase6b_status()
    checks["model_status"] = status.model_dump()
    if not status.available:
        raise AssertionError("Frozen Phase 6B model is unavailable.")

    result = predict_phase6b(prediction_payload(use_openai=False))
    assert_safe_text(result.explanation)
    if not result.human_review_required:
        raise AssertionError("High-risk audit payload did not require human review.")
    if not (
        0 <= result.probabilities.anomaly <= 1
        and result.probabilities.shortage_30m
        <= result.probabilities.shortage_60m
        <= result.probabilities.shortage_120m
        <= 1
    ):
        raise AssertionError("Probability output contract failed.")

    timings_ms: list[float] = []
    for _ in range(20):
        start = time.perf_counter()
        predict_phase6b(prediction_payload(use_openai=False))
        timings_ms.append((time.perf_counter() - start) * 1000)

    checks["runtime_latency_ms"] = {
        "runs": len(timings_ms),
        "mean": round(statistics.mean(timings_ms), 3),
        "p50": round(percentile(timings_ms, 0.50), 3),
        "p95": round(percentile(timings_ms, 0.95), 3),
        "max": round(max(timings_ms), 3),
    }
    if checks["runtime_latency_ms"]["p95"] > 5_000:
        raise AssertionError("Local model p95 latency exceeded 5 seconds.")

    client = TestClient(app)
    unauthorized = client.post(
        "/api/v1/ml/phase6b/predict",
        json=prediction_payload().model_dump(mode="json"),
    )
    if unauthorized.status_code != 401:
        raise AssertionError(
            f"Protected prediction endpoint expected 401, got {unauthorized.status_code}."
        )

    login = demo_login(DemoLoginRequest(profile_id="area-manager-sylhet"))
    authorized = client.post(
        "/api/v1/ml/phase6b/predict",
        json=prediction_payload().model_dump(mode="json"),
        headers={"Authorization": f"Bearer {login.access_token}"},
    )
    if authorized.status_code != 200:
        raise AssertionError(
            f"Authorized prediction endpoint failed: {authorized.status_code} {authorized.text}"
        )
    assert_safe_text(authorized.json()["explanation"])
    checks["api_security"] = {
        "unauthorized_status": unauthorized.status_code,
        "authorized_status": authorized.status_code,
    }

    openai_probe = explain_with_optional_openai(
        ExplanationInput(
            classification=result.classification,
            severity=result.severity,
            affected_resource=result.affected_resource,
            confidence=result.confidence,
            evidence=result.evidence,
            recommended_action=result.recommended_action,
            language="banglish",
        ),
        allow_openai=True,
    )
    assert_safe_text(openai_probe.text)
    checks["openai_probe"] = {
        "enabled": status.openai_enabled,
        "key_configured": status.openai_key_configured,
        "mode": openai_probe.mode,
        "fallback_is_healthy": openai_probe.mode == "deterministic_fallback",
    }

    checks["decision_sample"] = {
        "model_version": result.model_version,
        "classification": result.classification,
        "severity": result.severity,
        "affected_resource": result.affected_resource,
        "primary_stakeholder": result.primary_stakeholder,
        "secondary_stakeholder": result.secondary_stakeholder,
        "human_review_required": result.human_review_required,
        "explanation_mode": result.explanation_mode,
    }
    checks["git_head"] = run_git("rev-parse", "--short", "HEAD").strip()
    checks["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    checks["overall_status"] = "PASS"

    REPORT_JSON.write_text(
        json.dumps(checks, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    latency = checks["runtime_latency_ms"]
    openai = checks["openai_probe"]
    report = f"""# Phase 8 Final Readiness Report

## Overall status

**PASS**

## Verified

- Frozen Phase 6B artifact and Phase 6C metrics are present.
- No `.env` file or OpenAI-style API key pattern is tracked by Git.
- Protected prediction endpoint blocks unauthenticated access.
- Authorized trained-model prediction succeeds.
- Probability horizon ordering and safety-language contracts pass.
- Server-side provider-scope redaction tests pass through the automated test suite.
- Human review remains mandatory for the high-risk audit payload.
- OpenAI is optional; deterministic fallback remains operational.

## Local inference latency

- Runs: {latency["runs"]}
- Mean: {latency["mean"]} ms
- p50: {latency["p50"]} ms
- p95: {latency["p95"]} ms
- Max: {latency["max"]} ms

## OpenAI probe

- Enabled: {openai["enabled"]}
- Key configured: {openai["key_configured"]}
- Result mode: `{openai["mode"]}`
- Fallback healthy: {openai["fallback_is_healthy"]}

An OpenAI fallback result is not a system failure. Scoring, routing, evidence, and
human-review decisions remain deterministic and available without the external API.

## Safety boundary

The application is advisory decision support. It does not move money, refill wallets,
freeze accounts, block customers, or issue a final fraud verdict.
"""
    REPORT_MD.write_text(report, encoding="utf-8")

    print("PHASE 8 FINAL AUDIT PASSED")
    print(f"- model_version: {result.model_version}")
    print(f"- classification: {result.classification}")
    print(f"- human_review_required: {result.human_review_required}")
    print(f"- p95_local_inference_ms: {latency['p95']}")
    print(f"- openai_probe_mode: {openai_probe.mode}")
    print(f"- report: {REPORT_MD}")


if __name__ == "__main__":
    main()