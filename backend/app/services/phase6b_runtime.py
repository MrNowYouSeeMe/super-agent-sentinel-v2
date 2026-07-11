from __future__ import annotations

import math
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, model_validator

from app.core.config import get_settings
from app.services.openai_explanation import ExplanationInput, explain_with_optional_openai

ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = ROOT / "artifacts" / "models" / "phase6b" / "phase6b_model_bundle.joblib"
METRICS_PATH = ROOT / "reports" / "model_evaluation" / "phase6c_blind_test_metrics.json"

CATEGORICAL_COLUMNS = ["agent_profile", "location_type", "provider_mix_shift"]
BASE_NUMERIC_COLUMNS = [
    "festival_flag",
    "salary_flag",
    "remittance_flag",
    "market_day_flag",
    "network_recovery_flag",
    "shared_cash_balance",
    "bkash_balance",
    "nagad_balance",
    "rocket_balance",
    "tx_count_5m",
    "cash_in_amount_5m",
    "cash_out_amount_5m",
    "net_cash_flow_5m",
    "velocity_vs_baseline",
    "repeated_amount_ratio",
    "unique_customer_ratio",
    "failure_rate",
    "duplicate_ratio",
    "missing_ratio",
    "out_of_order_ratio",
    "feed_age_seconds",
    "reconciliation_difference",
    "data_quality_score",
    "shared_cash_burn_15m",
    "shared_cash_burn_30m",
    "shared_cash_burn_60m",
    "bkash_burn_60m",
    "nagad_burn_60m",
    "rocket_burn_60m",
]
DERIVED_NUMERIC_COLUMNS = [
    "hour_sin",
    "hour_cos",
    "dow_sin",
    "dow_cos",
    "month_sin",
    "month_cos",
    "weekend_flag",
    "rush_context_count",
    "cash_out_to_in_ratio",
    "abs_net_cash_flow_5m",
    "min_provider_balance",
    "provider_balance_spread",
    "shared_cash_to_outflow_ratio",
    "shared_cash_burn_to_balance_60m",
    "max_provider_burn_60m",
    "max_provider_burn_to_balance_60m",
    "quality_risk_score",
    "concentration_risk_score",
    "velocity_concentration_interaction",
    "failure_velocity_interaction",
]
NUMERIC_COLUMNS = BASE_NUMERIC_COLUMNS + DERIVED_NUMERIC_COLUMNS
ALLOWED_SERVICES = {"none", "shared_cash", "bkash", "nagad", "rocket"}


class Phase6BPredictionRequest(BaseModel):
    episode_id: str = Field(default="live-demo", min_length=2, max_length=100)
    window_id: str = Field(default="live-window", min_length=2, max_length=100)
    timestamp: datetime
    area_id: str = Field(min_length=2, max_length=64)
    outlet_id: str = Field(min_length=2, max_length=64)

    agent_profile: str = Field(default="standard", min_length=1, max_length=64)
    location_type: str = Field(default="urban", min_length=1, max_length=64)
    provider_mix_shift: str = Field(default="none", min_length=1, max_length=64)

    festival_flag: int = Field(default=0, ge=0, le=1)
    salary_flag: int = Field(default=0, ge=0, le=1)
    remittance_flag: int = Field(default=0, ge=0, le=1)
    market_day_flag: int = Field(default=0, ge=0, le=1)
    network_recovery_flag: int = Field(default=0, ge=0, le=1)

    shared_cash_balance: float = Field(ge=0)
    bkash_balance: float = Field(ge=0)
    nagad_balance: float = Field(ge=0)
    rocket_balance: float = Field(ge=0)

    tx_count_5m: int = Field(ge=0)
    cash_in_amount_5m: float = Field(ge=0)
    cash_out_amount_5m: float = Field(ge=0)
    net_cash_flow_5m: float
    velocity_vs_baseline: float = Field(ge=0)

    repeated_amount_ratio: float = Field(ge=0, le=1)
    unique_customer_ratio: float = Field(ge=0, le=1)
    failure_rate: float = Field(ge=0, le=1)
    duplicate_ratio: float = Field(ge=0, le=1)
    missing_ratio: float = Field(ge=0, le=1)
    out_of_order_ratio: float = Field(ge=0, le=1)

    feed_age_seconds: float = Field(ge=0)
    reconciliation_difference: float = Field(ge=0)
    data_quality_score: float = Field(ge=0, le=1)

    shared_cash_burn_15m: float
    shared_cash_burn_30m: float
    shared_cash_burn_60m: float
    bkash_burn_60m: float
    nagad_burn_60m: float
    rocket_burn_60m: float

    language: Literal["en", "bn", "banglish"] = "banglish"
    use_openai_explanation: bool = False

    @model_validator(mode="after")
    def validate_semantics(self) -> "Phase6BPredictionRequest":
        expected_net = self.cash_in_amount_5m - self.cash_out_amount_5m
        tolerance = max(100.0, 0.02 * max(self.cash_in_amount_5m, self.cash_out_amount_5m, 1.0))
        if abs(self.net_cash_flow_5m - expected_net) > tolerance:
            # This is allowed because source feeds may differ, but it becomes evidence/data-quality context.
            return self
        return self


class ProbabilitySet(BaseModel):
    anomaly: float = Field(ge=0, le=1)
    shortage_30m: float = Field(ge=0, le=1)
    shortage_60m: float = Field(ge=0, le=1)
    shortage_120m: float = Field(ge=0, le=1)


class Phase6BPredictionResponse(BaseModel):
    model_version: str
    classification: str
    severity: str
    affected_resource: str
    probabilities: ProbabilitySet
    estimated_time_to_shortage_minutes: float | None
    confidence: float = Field(ge=0, le=1)
    data_health: str
    data_verification_required: bool
    human_review_required: bool
    anomaly_requires_review: bool
    shortage_requires_review: bool
    primary_stakeholder: str
    secondary_stakeholder: str
    stakeholder_visibility: list[str]
    evidence: list[str]
    validation_warnings: list[str]
    recommended_action: str
    explanation: str
    explanation_mode: str
    safety_boundary: str


class Phase6BStatus(BaseModel):
    available: bool
    model_path: str
    model_version: str | None
    phase6c_metrics_available: bool
    openai_enabled: bool
    openai_key_configured: bool
    safety_boundary: str


def _safe_divide(numerator: pd.Series, denominator: pd.Series | float, floor: float = 1.0) -> pd.Series:
    if isinstance(denominator, pd.Series):
        den = denominator.abs().clip(lower=floor)
    else:
        den = max(abs(float(denominator)), floor)
    return numerator / den


def _engineer_features(frame: pd.DataFrame) -> pd.DataFrame:
    df = frame.copy()
    timestamps = pd.to_datetime(df["timestamp"], errors="coerce")
    if timestamps.isna().any():
        raise ValueError("Invalid timestamp supplied.")

    for column in CATEGORICAL_COLUMNS:
        df[column] = df[column].fillna("unknown").astype(str)

    hour = timestamps.dt.hour.astype(float)
    dow = timestamps.dt.dayofweek.astype(float)
    month = timestamps.dt.month.astype(float)
    df["hour_sin"] = np.sin(2.0 * np.pi * hour / 24.0)
    df["hour_cos"] = np.cos(2.0 * np.pi * hour / 24.0)
    df["dow_sin"] = np.sin(2.0 * np.pi * dow / 7.0)
    df["dow_cos"] = np.cos(2.0 * np.pi * dow / 7.0)
    df["month_sin"] = np.sin(2.0 * np.pi * (month - 1.0) / 12.0)
    df["month_cos"] = np.cos(2.0 * np.pi * (month - 1.0) / 12.0)
    df["weekend_flag"] = (dow >= 5).astype(float)

    context_cols = [
        "festival_flag",
        "salary_flag",
        "remittance_flag",
        "market_day_flag",
        "network_recovery_flag",
    ]
    df["rush_context_count"] = df[context_cols].fillna(0).sum(axis=1).astype(float)
    df["cash_out_to_in_ratio"] = _safe_divide(
        df["cash_out_amount_5m"] + 1.0,
        df["cash_in_amount_5m"] + 1.0,
    )
    df["abs_net_cash_flow_5m"] = df["net_cash_flow_5m"].abs()

    provider_balances = df[["bkash_balance", "nagad_balance", "rocket_balance"]]
    df["min_provider_balance"] = provider_balances.min(axis=1)
    df["provider_balance_spread"] = provider_balances.max(axis=1) - provider_balances.min(axis=1)
    df["shared_cash_to_outflow_ratio"] = _safe_divide(
        df["shared_cash_balance"],
        df["cash_out_amount_5m"] + 1.0,
    )
    df["shared_cash_burn_to_balance_60m"] = _safe_divide(
        df["shared_cash_burn_60m"].clip(lower=0),
        df["shared_cash_balance"] + 1.0,
    )

    provider_burns = df[["bkash_burn_60m", "nagad_burn_60m", "rocket_burn_60m"]].clip(lower=0)
    df["max_provider_burn_60m"] = provider_burns.max(axis=1)
    burn_ratios = pd.DataFrame(
        {
            "bkash": _safe_divide(provider_burns["bkash_burn_60m"], df["bkash_balance"] + 1.0),
            "nagad": _safe_divide(provider_burns["nagad_burn_60m"], df["nagad_balance"] + 1.0),
            "rocket": _safe_divide(provider_burns["rocket_burn_60m"], df["rocket_balance"] + 1.0),
        }
    )
    df["max_provider_burn_to_balance_60m"] = burn_ratios.max(axis=1)

    df["quality_risk_score"] = (
        (1.0 - df["data_quality_score"].clip(0, 1))
        + df["missing_ratio"].clip(0, 1)
        + df["duplicate_ratio"].clip(0, 1)
        + df["out_of_order_ratio"].clip(0, 1)
        + (df["feed_age_seconds"].clip(lower=0) / 1800.0).clip(upper=2.0)
        + _safe_divide(
            df["reconciliation_difference"].clip(lower=0),
            df["shared_cash_balance"] + 1.0,
        )
    )
    df["concentration_risk_score"] = (
        df["repeated_amount_ratio"].clip(0, 1)
        + (1.0 - df["unique_customer_ratio"].clip(0, 1))
    ) / 2.0
    df["velocity_concentration_interaction"] = (
        df["velocity_vs_baseline"].clip(lower=0, upper=20)
        * df["concentration_risk_score"]
    )
    df["failure_velocity_interaction"] = (
        df["failure_rate"].clip(0, 1)
        * df["velocity_vs_baseline"].clip(lower=0, upper=20)
    )

    for column in NUMERIC_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")
        df[column] = df[column].replace([np.inf, -np.inf], np.nan)

    return df


def _rule_anomaly_score(df: pd.DataFrame) -> np.ndarray:
    velocity = np.clip((df["velocity_vs_baseline"].to_numpy(float) - 1.0) / 5.0, 0.0, 1.0)
    repeated = np.clip(df["repeated_amount_ratio"].to_numpy(float), 0.0, 1.0)
    concentration = np.clip(1.0 - df["unique_customer_ratio"].to_numpy(float), 0.0, 1.0)
    failure = np.clip(df["failure_rate"].to_numpy(float) * 4.0, 0.0, 1.0)
    quality = np.clip(1.0 - df["data_quality_score"].to_numpy(float), 0.0, 1.0)
    score = 0.28 * velocity + 0.25 * repeated + 0.20 * concentration + 0.17 * failure + 0.10 * quality
    rush = df["rush_context_count"].to_numpy(float) > 0
    healthy = df["data_quality_score"].to_numpy(float) >= 0.85
    score = score - np.where(rush & healthy, 0.08, 0.0)
    return np.clip(score, 0.0, 1.0)


def _rule_shortage_score(df: pd.DataFrame, horizon: int) -> np.ndarray:
    eps = 1.0
    shared_burn = np.clip(df["shared_cash_burn_60m"].to_numpy(float), 0.0, None)
    shared_runway = np.where(
        shared_burn > 0,
        df["shared_cash_balance"].to_numpy(float) / np.maximum(shared_burn / 60.0, eps),
        9999.0,
    )
    provider_runs = []
    for provider in ("bkash", "nagad", "rocket"):
        burn = np.clip(df[f"{provider}_burn_60m"].to_numpy(float), 0.0, None)
        balance = df[f"{provider}_balance"].to_numpy(float)
        provider_runs.append(np.where(burn > 0, balance / np.maximum(burn / 60.0, eps), 9999.0))
    min_runway = np.minimum.reduce([shared_runway, *provider_runs])
    scale = max(horizon * 0.20, 8.0)
    score = 1.0 / (1.0 + np.exp(np.clip((min_runway - horizon) / scale, -30, 30)))
    quality = np.clip(df["data_quality_score"].to_numpy(float), 0.25, 1.0)
    return np.clip(score * (0.75 + 0.25 * quality), 0.0, 1.0)


def _deterministic_affected_service(df: pd.DataFrame) -> str:
    row = df.iloc[0]
    candidates: dict[str, float] = {}
    for service, balance_column, burn_column in (
        ("shared_cash", "shared_cash_balance", "shared_cash_burn_60m"),
        ("bkash", "bkash_balance", "bkash_burn_60m"),
        ("nagad", "nagad_balance", "nagad_burn_60m"),
        ("rocket", "rocket_balance", "rocket_burn_60m"),
    ):
        burn = max(float(row[burn_column]), 0.0)
        balance = max(float(row[balance_column]), 0.0)
        candidates[service] = balance / max(burn / 60.0, 1.0) if burn > 0 else 9999.0
    return min(candidates, key=candidates.get)


def _stakeholder_route(
    *,
    anomaly: bool,
    shortage: bool,
    data_issue: bool,
    service: str,
    high_severity: bool,
) -> tuple[str, str, list[str]]:
    visibility: list[str] = []

    if data_issue and not anomaly and not shortage:
        primary, secondary = "data_operations", "area_manager"
    elif anomaly and shortage:
        primary, secondary = "area_manager", "risk_reviewer"
        if service in {"bkash", "nagad", "rocket"}:
            visibility.append(f"{service}_operations")
    elif shortage:
        primary = "area_manager"
        secondary = "outlet_operator" if service == "shared_cash" else f"{service}_operations"
    elif anomaly:
        primary = "risk_reviewer"
        secondary = f"{service}_operations" if service in {"bkash", "nagad", "rocket"} else "area_manager"
    else:
        primary, secondary = "outlet_operator", "area_manager"

    visibility.extend([primary, secondary])
    if data_issue:
        visibility.append("data_operations")
    if high_severity:
        visibility.append("central_operations")

    ordered: list[str] = []
    for item in visibility:
        if item and item not in ordered:
            ordered.append(item)
    return primary, secondary, ordered


def _validation_warnings(payload: Phase6BPredictionRequest) -> list[str]:
    warnings: list[str] = []
    expected_net = payload.cash_in_amount_5m - payload.cash_out_amount_5m
    tolerance = max(100.0, 0.02 * max(payload.cash_in_amount_5m, payload.cash_out_amount_5m, 1.0))
    if abs(payload.net_cash_flow_5m - expected_net) > tolerance:
        warnings.append("Net cash flow does not reconcile with cash-in minus cash-out.")
    if payload.tx_count_5m == 0 and (payload.cash_in_amount_5m > 0 or payload.cash_out_amount_5m > 0):
        warnings.append("Transaction amount exists while transaction count is zero.")
    if payload.feed_age_seconds > 900:
        warnings.append("Provider feed is stale; verify data before operational escalation.")
    if payload.reconciliation_difference > 25_000:
        warnings.append("Reconciliation difference exceeds the local review threshold.")
    if payload.data_quality_score < 0.60 or payload.missing_ratio >= 0.20:
        warnings.append("Input data quality is degraded.")
    return warnings


def _evidence(payload: Phase6BPredictionRequest, affected_service: str, warnings: list[str]) -> list[str]:
    evidence: list[str] = []
    if payload.velocity_vs_baseline >= 2.0:
        evidence.append(f"Transaction velocity is {payload.velocity_vs_baseline:.2f}x the expected baseline.")
    if payload.repeated_amount_ratio >= 0.45:
        evidence.append(f"Repeated/near-identical amount ratio is {payload.repeated_amount_ratio:.1%}.")
    if payload.unique_customer_ratio <= 0.35:
        evidence.append(f"Unique-customer ratio is low at {payload.unique_customer_ratio:.1%}.")
    if payload.failure_rate >= 0.10:
        evidence.append(f"Failure rate is elevated at {payload.failure_rate:.1%}.")
    if affected_service != "none":
        evidence.append(f"Lowest estimated liquidity runway is associated with {affected_service}.")
    context_count = sum(
        [
            payload.festival_flag,
            payload.salary_flag,
            payload.remittance_flag,
            payload.market_day_flag,
            payload.network_recovery_flag,
        ]
    )
    if context_count:
        evidence.append("Rush context is active, so legitimate demand is considered before escalation.")
    evidence.extend(warnings[:2])
    if not evidence:
        evidence.append("No strong rule-level warning was found; continue normal monitoring.")
    return evidence[:6]


@lru_cache(maxsize=1)
def load_phase6b_bundle() -> dict[str, Any]:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Phase 6B model bundle is missing: {MODEL_PATH}")
    bundle = joblib.load(MODEL_PATH)
    required = {"model_version", "preprocessor", "binary_models", "safety_boundary"}
    missing = required - set(bundle)
    if missing:
        raise ValueError(f"Model bundle contract is incomplete: {sorted(missing)}")
    return bundle


def phase6b_status() -> Phase6BStatus:
    settings = get_settings()
    model_version: str | None = None
    available = MODEL_PATH.exists()
    if available:
        try:
            model_version = str(load_phase6b_bundle()["model_version"])
        except Exception:
            available = False
    return Phase6BStatus(
        available=available,
        model_path=str(MODEL_PATH),
        model_version=model_version,
        phase6c_metrics_available=METRICS_PATH.exists(),
        openai_enabled=settings.openai_enabled,
        openai_key_configured=bool(settings.openai_api_key),
        safety_boundary=(
            "The trained model provides advisory scores and stakeholder routing only. "
            "A human reviewer remains the final decision maker."
        ),
    )


def _validate_output(
    probabilities: dict[str, float],
    eta: float | None,
    affected_service: str,
) -> None:
    for name, value in probabilities.items():
        if not math.isfinite(value) or value < 0 or value > 1:
            raise ValueError(f"Invalid probability output for {name}: {value}")
    if not (
        probabilities["shortage_30m"]
        <= probabilities["shortage_60m"]
        <= probabilities["shortage_120m"]
    ):
        raise ValueError("Shortage probabilities violate horizon monotonicity.")
    if eta is not None and (not math.isfinite(eta) or eta < 0 or eta > 120):
        raise ValueError("ETA output is outside the validated 0-120 minute range.")
    if affected_service not in ALLOWED_SERVICES:
        raise ValueError(f"Unexpected affected service: {affected_service}")


def predict_phase6b(payload: Phase6BPredictionRequest) -> Phase6BPredictionResponse:
    bundle = load_phase6b_bundle()
    raw = payload.model_dump(mode="json")
    raw["timestamp"] = payload.timestamp.isoformat()
    frame = _engineer_features(pd.DataFrame([raw]))
    transformed = bundle["preprocessor"].transform(frame)

    scores: dict[str, float] = {}
    for name, model_payload in bundle["binary_models"].items():
        estimator = model_payload["estimator"]
        calibrator = model_payload["calibrator"]
        raw_probability = float(estimator.predict_proba(transformed)[0, 1])
        calibrated = float(calibrator.predict([raw_probability])[0])
        if name == "anomaly":
            rule_probability = float(_rule_anomaly_score(frame)[0])
        else:
            horizon = int(name.split("_")[1].replace("m", ""))
            rule_probability = float(_rule_shortage_score(frame, horizon)[0])
        ml_weight = float(model_payload["hybrid_weight_ml"])
        scores[name] = float(np.clip(ml_weight * calibrated + (1.0 - ml_weight) * rule_probability, 0, 1))

    shortage_30 = scores["shortage_30m"]
    shortage_60 = max(shortage_30, scores["shortage_60m"])
    shortage_120 = max(shortage_60, scores["shortage_120m"])
    anomaly_probability = scores["anomaly"]

    thresholds = {
        name: float(model_payload["threshold"])
        for name, model_payload in bundle["binary_models"].items()
    }
    anomaly_flag = anomaly_probability >= thresholds["anomaly"]
    shortage_30_flag = shortage_30 >= thresholds["shortage_30m"]
    shortage_flag = shortage_60 >= thresholds["shortage_60m"]
    shortage_120_flag = shortage_120 >= thresholds["shortage_120m"]

    data_issue = bool(
        payload.data_quality_score < 0.60
        or payload.missing_ratio >= 0.20
        or payload.feed_age_seconds > 900
        or payload.reconciliation_difference > 25_000
    )

    affected_service = "none"
    if shortage_120_flag:
        service_model = bundle.get("affected_service_model")
        if service_model is not None:
            affected_service = str(service_model.predict(transformed)[0])
        if affected_service not in ALLOWED_SERVICES or affected_service == "none":
            affected_service = _deterministic_affected_service(frame)

    eta: float | None = None
    if shortage_120_flag and bundle.get("eta_model") is not None:
        eta = float(np.clip(bundle["eta_model"].predict(transformed)[0], 0.0, 120.0))

    if data_issue and not anomaly_flag and not shortage_flag:
        classification = "data_quality_issue"
    elif anomaly_flag and shortage_flag:
        classification = "liquidity_pressure_with_unusual_activity"
    elif shortage_flag:
        classification = "liquidity_pressure"
    elif anomaly_flag:
        classification = "unusual_activity"
    else:
        classification = "normal_operation"

    max_risk = max(anomaly_probability, shortage_30, shortage_60, shortage_120)
    if max_risk >= 0.85 or shortage_30_flag:
        severity = "high"
    elif anomaly_flag or shortage_flag or data_issue:
        severity = "medium"
    else:
        severity = "low"

    high_severity = severity == "high"
    primary, secondary, visibility = _stakeholder_route(
        anomaly=anomaly_flag,
        shortage=shortage_flag,
        data_issue=data_issue,
        service=affected_service,
        high_severity=high_severity,
    )
    warnings = _validation_warnings(payload)
    evidence = _evidence(payload, affected_service, warnings)
    human_review_required = bool(anomaly_flag or shortage_flag or data_issue)

    if data_issue:
        recommended_action = "Verify source feed and reconciliation before relying on the alert."
    elif anomaly_flag and shortage_flag:
        recommended_action = "Area manager and risk reviewer should jointly verify the outlet and affected provider."
    elif shortage_flag:
        recommended_action = "Area manager should verify current liquidity and coordinate approved operational support."
    elif anomaly_flag:
        recommended_action = "Risk reviewer should inspect evidence and legitimate rush context."
    else:
        recommended_action = "Continue normal monitoring."

    confidence = float(np.clip(max_risk * (0.55 + 0.45 * payload.data_quality_score), 0.0, 1.0))
    explanation_result = explain_with_optional_openai(
        ExplanationInput(
            classification=classification,
            severity=severity,
            affected_resource=affected_service,
            confidence=confidence,
            evidence=evidence,
            recommended_action=recommended_action,
            language=payload.language,
        ),
        allow_openai=payload.use_openai_explanation,
    )

    probability_payload = {
        "anomaly": anomaly_probability,
        "shortage_30m": shortage_30,
        "shortage_60m": shortage_60,
        "shortage_120m": shortage_120,
    }
    _validate_output(probability_payload, eta, affected_service)

    return Phase6BPredictionResponse(
        model_version=str(bundle["model_version"]),
        classification=classification,
        severity=severity,
        affected_resource=affected_service,
        probabilities=ProbabilitySet(**probability_payload),
        estimated_time_to_shortage_minutes=eta,
        confidence=confidence,
        data_health="degraded" if data_issue else "healthy",
        data_verification_required=data_issue,
        human_review_required=human_review_required,
        anomaly_requires_review=anomaly_flag,
        shortage_requires_review=shortage_flag,
        primary_stakeholder=primary,
        secondary_stakeholder=secondary,
        stakeholder_visibility=visibility,
        evidence=evidence,
        validation_warnings=warnings,
        recommended_action=recommended_action,
        explanation=explanation_result.text,
        explanation_mode=explanation_result.mode,
        safety_boundary=str(bundle["safety_boundary"]),
    )