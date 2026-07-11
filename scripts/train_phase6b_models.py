from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    fbeta_score,
    log_loss,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

RANDOM_STATE = 20260711

ID_COLUMNS = ["episode_id", "window_id", "timestamp"]
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
FEATURE_COLUMNS = CATEGORICAL_COLUMNS + NUMERIC_COLUMNS

TARGETS = {
    "anomaly": "is_unusual",
    "shortage_30m": "shortage_within_30m",
    "shortage_60m": "shortage_within_60m",
    "shortage_120m": "shortage_within_120m",
}
FORBIDDEN_TRAINING_FEATURE_PREFIXES = ("future_", "approved_")
FORBIDDEN_TRAINING_FEATURES = {
    "is_unusual",
    "scenario_family",
    "anomaly_type",
    "severity",
    "hard_negative_flag",
    "data_quality_issue_flag",
    "shortage_within_30m",
    "shortage_within_60m",
    "shortage_within_120m",
    "actual_time_to_shortage_minutes",
    "affected_service",
    "label_confidence",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def safe_divide(numerator: pd.Series, denominator: pd.Series | float, floor: float = 1.0) -> pd.Series:
    if isinstance(denominator, pd.Series):
        den = denominator.abs().clip(lower=floor)
    else:
        den = max(abs(float(denominator)), floor)
    return numerator / den


def validate_raw_schema(train: pd.DataFrame, public: pd.DataFrame) -> None:
    required_public = set(ID_COLUMNS + CATEGORICAL_COLUMNS + BASE_NUMERIC_COLUMNS)
    missing_train = sorted(required_public - set(train.columns))
    missing_public = sorted(required_public - set(public.columns))
    if missing_train:
        raise ValueError(f"Training benchmark missing required public features: {missing_train}")
    if missing_public:
        raise ValueError(f"Public blind-test benchmark missing required features: {missing_public}")
    for target in TARGETS.values():
        if target not in train.columns:
            raise ValueError(f"Training target is missing: {target}")
        if target in public.columns:
            raise ValueError(f"Blind public data unexpectedly exposes target: {target}")
    leaked = [
        name
        for name in FEATURE_COLUMNS
        if name in FORBIDDEN_TRAINING_FEATURES or name.startswith(FORBIDDEN_TRAINING_FEATURE_PREFIXES)
    ]
    if leaked:
        raise ValueError(f"Feature contract contains leakage-prone columns: {leaked}")


def engineer_features(frame: pd.DataFrame) -> pd.DataFrame:
    df = frame.copy()
    timestamps = pd.to_datetime(df["timestamp"], errors="coerce")
    if timestamps.isna().any():
        raise ValueError(f"Invalid timestamps found: {int(timestamps.isna().sum())}")

    df["provider_mix_shift"] = df["provider_mix_shift"].fillna("none").astype(str)
    df["agent_profile"] = df["agent_profile"].fillna("unknown").astype(str)
    df["location_type"] = df["location_type"].fillna("unknown").astype(str)

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
    df["cash_out_to_in_ratio"] = safe_divide(df["cash_out_amount_5m"] + 1.0, df["cash_in_amount_5m"] + 1.0)
    df["abs_net_cash_flow_5m"] = df["net_cash_flow_5m"].abs()

    provider_balances = df[["bkash_balance", "nagad_balance", "rocket_balance"]]
    df["min_provider_balance"] = provider_balances.min(axis=1)
    df["provider_balance_spread"] = provider_balances.max(axis=1) - provider_balances.min(axis=1)
    df["shared_cash_to_outflow_ratio"] = safe_divide(df["shared_cash_balance"], df["cash_out_amount_5m"] + 1.0)
    df["shared_cash_burn_to_balance_60m"] = safe_divide(
        df["shared_cash_burn_60m"].clip(lower=0), df["shared_cash_balance"] + 1.0
    )

    provider_burns = df[["bkash_burn_60m", "nagad_burn_60m", "rocket_burn_60m"]].clip(lower=0)
    df["max_provider_burn_60m"] = provider_burns.max(axis=1)
    burn_ratios = pd.DataFrame(
        {
            "bkash": safe_divide(provider_burns["bkash_burn_60m"], df["bkash_balance"] + 1.0),
            "nagad": safe_divide(provider_burns["nagad_burn_60m"], df["nagad_balance"] + 1.0),
            "rocket": safe_divide(provider_burns["rocket_burn_60m"], df["rocket_balance"] + 1.0),
        }
    )
    df["max_provider_burn_to_balance_60m"] = burn_ratios.max(axis=1)

    df["quality_risk_score"] = (
        (1.0 - df["data_quality_score"].clip(0, 1))
        + df["missing_ratio"].clip(0, 1)
        + df["duplicate_ratio"].clip(0, 1)
        + df["out_of_order_ratio"].clip(0, 1)
        + (df["feed_age_seconds"].clip(lower=0) / 1800.0).clip(upper=2.0)
        + safe_divide(df["reconciliation_difference"].clip(lower=0), df["shared_cash_balance"] + 1.0)
    )
    df["concentration_risk_score"] = (
        df["repeated_amount_ratio"].clip(0, 1) + (1.0 - df["unique_customer_ratio"].clip(0, 1))
    ) / 2.0
    df["velocity_concentration_interaction"] = (
        df["velocity_vs_baseline"].clip(lower=0, upper=20) * df["concentration_risk_score"]
    )
    df["failure_velocity_interaction"] = (
        df["failure_rate"].clip(0, 1) * df["velocity_vs_baseline"].clip(lower=0, upper=20)
    )

    for column in NUMERIC_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")
        df[column] = df[column].replace([np.inf, -np.inf], np.nan)

    return df


def episode_bucket(value: str) -> int:
    digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def add_split(frame: pd.DataFrame) -> pd.DataFrame:
    df = frame.copy()
    buckets = df["episode_id"].astype(str).map(episode_bucket)
    df["_model_split"] = np.select(
        [buckets < 70, buckets < 85],
        ["train", "calibration"],
        default="validation",
    )
    return df


def make_preprocessor() -> ColumnTransformer:
    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
        ]
    )
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("numeric", numeric_pipeline, NUMERIC_COLUMNS),
            ("categorical", categorical_pipeline, CATEGORICAL_COLUMNS),
        ],
        remainder="drop",
        sparse_threshold=0.0,
        verbose_feature_names_out=True,
    )


def binary_metrics(y_true: np.ndarray, probabilities: np.ndarray, threshold: float) -> dict[str, Any]:
    y = np.asarray(y_true, dtype=int)
    p = np.clip(np.asarray(probabilities, dtype=float), 0.0, 1.0)
    pred = (p >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    fpr = fp / max(fp + tn, 1)
    fnr = fn / max(fn + tp, 1)
    result: dict[str, Any] = {
        "threshold": round(float(threshold), 6),
        "rows": int(len(y)),
        "positives": int(y.sum()),
        "positive_rate": round(float(y.mean()) if len(y) else 0.0, 8),
        "precision": round(float(precision_score(y, pred, zero_division=0)), 6),
        "recall": round(float(recall_score(y, pred, zero_division=0)), 6),
        "f1": round(float(f1_score(y, pred, zero_division=0)), 6),
        "f2": round(float(fbeta_score(y, pred, beta=2, zero_division=0)), 6),
        "accuracy": round(float(accuracy_score(y, pred)), 6),
        "balanced_accuracy": round(float(balanced_accuracy_score(y, pred)), 6),
        "false_positive_rate": round(float(fpr), 6),
        "false_negative_rate": round(float(fnr), 6),
        "brier_score": round(float(brier_score_loss(y, p)), 6),
        "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }
    if len(np.unique(y)) > 1:
        result["pr_auc"] = round(float(average_precision_score(y, p)), 6)
        result["roc_auc"] = round(float(roc_auc_score(y, p)), 6)
    else:
        result["pr_auc"] = None
        result["roc_auc"] = None
    return result


def subgroup_fpr(y_true: np.ndarray, probabilities: np.ndarray, threshold: float, mask: np.ndarray) -> float | None:
    y = np.asarray(y_true, dtype=int)[mask]
    if len(y) == 0:
        return None
    pred = (np.asarray(probabilities)[mask] >= threshold).astype(int)
    negatives = y == 0
    if negatives.sum() == 0:
        return None
    return float((pred[negatives] == 1).mean())


def choose_threshold(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    *,
    hard_negative_mask: np.ndarray,
    context_mask: np.ndarray,
    task_name: str,
) -> tuple[float, dict[str, Any]]:
    y = np.asarray(y_true, dtype=np.int8)
    p = np.clip(np.asarray(probabilities, dtype=float), 0.0, 1.0)
    candidates = np.unique(
        np.concatenate(
            [
                np.linspace(0.05, 0.95, 61),
                np.quantile(p, np.linspace(0.05, 0.95, 20)),
            ]
        )
    )
    predictions = p[:, None] >= candidates[None, :]
    positive = y == 1
    negative = ~positive
    tp = np.sum(predictions & positive[:, None], axis=0).astype(float)
    fp = np.sum(predictions & negative[:, None], axis=0).astype(float)
    fn = np.sum((~predictions) & positive[:, None], axis=0).astype(float)
    tn = np.sum((~predictions) & negative[:, None], axis=0).astype(float)

    precision = tp / np.maximum(tp + fp, 1.0)
    recall = tp / np.maximum(tp + fn, 1.0)
    f2 = 5.0 * tp / np.maximum(5.0 * tp + 4.0 * fn + fp, 1.0)
    fpr = fp / np.maximum(fp + tn, 1.0)

    hard_negatives = np.asarray(hard_negative_mask, dtype=bool) & negative
    if hard_negatives.any():
        hard_fpr = np.mean(predictions[hard_negatives], axis=0)
    else:
        hard_fpr = np.zeros_like(candidates)
    context_negatives = np.asarray(context_mask, dtype=bool) & negative
    if context_negatives.any():
        context_fpr = np.mean(predictions[context_negatives], axis=0)
    else:
        context_fpr = np.zeros_like(candidates)

    max_fpr = 0.10 if task_name == "anomaly" else 0.08
    max_hard_fpr = 0.12 if task_name == "anomaly" else 0.08
    objective = (
        f2
        - np.maximum(0.0, fpr - max_fpr) * 2.5
        - np.maximum(0.0, hard_fpr - max_hard_fpr) * 2.0
        - np.maximum(0.0, context_fpr - max_hard_fpr) * 1.5
        - np.maximum(0.0, 0.40 - precision) * 0.8
    )
    tie_break = precision + 0.2 * recall
    order = np.lexsort((tie_break, objective))
    best_index = int(order[-1])
    threshold = float(candidates[best_index])
    metrics = binary_metrics(y, p, threshold)
    metrics["hard_negative_fpr"] = round(float(hard_fpr[best_index]), 6)
    metrics["contextual_rush_fpr"] = round(float(context_fpr[best_index]), 6)
    metrics["selection_objective"] = round(float(objective[best_index]), 6)
    return threshold, metrics


def calibrate(raw_probabilities: np.ndarray, y_cal: np.ndarray) -> IsotonicRegression:
    calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    calibrator.fit(np.asarray(raw_probabilities, dtype=float), np.asarray(y_cal, dtype=int))
    return calibrator


def rule_anomaly_score(df: pd.DataFrame) -> np.ndarray:
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


def rule_shortage_score(df: pd.DataFrame, horizon: int) -> np.ndarray:
    eps = 1.0
    shared_burn = np.clip(df["shared_cash_burn_60m"].to_numpy(float), 0.0, None)
    shared_runway = np.where(shared_burn > 0, df["shared_cash_balance"].to_numpy(float) / np.maximum(shared_burn / 60.0, eps), 9999.0)
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


@dataclass
class BinaryBundleResult:
    name: str
    estimator: HistGradientBoostingClassifier
    calibrator: IsotonicRegression
    threshold: float
    calibration_metrics: dict[str, Any]
    validation_metrics: dict[str, Any]
    rule_validation_metrics: dict[str, Any]
    hybrid_validation_metrics: dict[str, Any]
    hybrid_weight_ml: float
    validation_probabilities: np.ndarray
    public_probabilities: np.ndarray


def train_binary_task(
    *,
    name: str,
    y_train: np.ndarray,
    y_cal: np.ndarray,
    y_val: np.ndarray,
    x_train: np.ndarray,
    x_cal: np.ndarray,
    x_val: np.ndarray,
    x_public: np.ndarray,
    cal_frame: pd.DataFrame,
    val_frame: pd.DataFrame,
    public_frame: pd.DataFrame,
    hard_train: np.ndarray,
    hard_cal: np.ndarray,
    hard_val: np.ndarray,
    context_cal: np.ndarray,
    context_val: np.ndarray,
) -> BinaryBundleResult:
    weights = compute_sample_weight(class_weight="balanced", y=y_train).astype(float)
    if name == "anomaly":
        weights = weights * np.where((y_train == 0) & hard_train, 2.0, 1.0)
    else:
        weights = weights * np.where((y_train == 0) & hard_train, 1.5, 1.0)

    estimator = HistGradientBoostingClassifier(
        learning_rate=0.07,
        max_iter=90,
        max_leaf_nodes=31,
        min_samples_leaf=35,
        l2_regularization=1.0,
        early_stopping=True,
        validation_fraction=0.12,
        n_iter_no_change=10,
        random_state=RANDOM_STATE,
    )
    estimator.fit(x_train, y_train, sample_weight=weights)

    raw_cal = estimator.predict_proba(x_cal)[:, 1]
    calibrator = calibrate(raw_cal, y_cal)
    cal_prob = np.asarray(calibrator.predict(raw_cal), dtype=float)
    threshold, selection = choose_threshold(
        y_cal,
        cal_prob,
        hard_negative_mask=hard_cal,
        context_mask=context_cal,
        task_name=name,
    )

    raw_val = estimator.predict_proba(x_val)[:, 1]
    val_prob = np.asarray(calibrator.predict(raw_val), dtype=float)
    validation = binary_metrics(y_val, val_prob, threshold)
    validation["hard_negative_fpr"] = subgroup_fpr(y_val, val_prob, threshold, hard_val)
    validation["contextual_rush_fpr"] = subgroup_fpr(y_val, val_prob, threshold, context_val)

    if name == "anomaly":
        rule_val = rule_anomaly_score(val_frame)
        rule_cal = rule_anomaly_score(cal_frame)
        rule_public = rule_anomaly_score(public_frame)
    else:
        horizon = int(name.split("_")[1].replace("m", ""))
        rule_val = rule_shortage_score(val_frame, horizon)
        rule_cal = rule_shortage_score(cal_frame, horizon)
        rule_public = rule_shortage_score(public_frame, horizon)

    rule_threshold, _ = choose_threshold(
        y_cal,
        rule_cal,
        hard_negative_mask=hard_cal,
        context_mask=context_cal,
        task_name=name,
    )
    rule_validation = binary_metrics(y_val, rule_val, rule_threshold)
    rule_validation["hard_negative_fpr"] = subgroup_fpr(y_val, rule_val, rule_threshold, hard_val)
    rule_validation["contextual_rush_fpr"] = subgroup_fpr(y_val, rule_val, rule_threshold, context_val)

    best_hybrid: tuple[float, float, dict[str, Any], float] | None = None
    for ml_weight in (0.60, 0.70, 0.80, 0.90):
        hybrid_cal = ml_weight * cal_prob + (1.0 - ml_weight) * rule_cal
        hybrid_threshold, hybrid_selection = choose_threshold(
            y_cal,
            hybrid_cal,
            hard_negative_mask=hard_cal,
            context_mask=context_cal,
            task_name=name,
        )
        objective = float(hybrid_selection["selection_objective"])
        if best_hybrid is None or objective > best_hybrid[0]:
            best_hybrid = (objective, hybrid_threshold, hybrid_selection, ml_weight)
    assert best_hybrid is not None
    hybrid_weight = best_hybrid[3]
    hybrid_threshold = best_hybrid[1]
    hybrid_val = hybrid_weight * val_prob + (1.0 - hybrid_weight) * rule_val
    hybrid_validation = binary_metrics(y_val, hybrid_val, hybrid_threshold)
    hybrid_validation["hard_negative_fpr"] = subgroup_fpr(y_val, hybrid_val, hybrid_threshold, hard_val)
    hybrid_validation["contextual_rush_fpr"] = subgroup_fpr(y_val, hybrid_val, hybrid_threshold, context_val)
    hybrid_validation["ml_weight"] = hybrid_weight
    hybrid_validation["rule_weight"] = round(1.0 - hybrid_weight, 6)

    raw_public = estimator.predict_proba(x_public)[:, 1]
    public_ml = np.asarray(calibrator.predict(raw_public), dtype=float)
    public_hybrid = np.clip(hybrid_weight * public_ml + (1.0 - hybrid_weight) * rule_public, 0.0, 1.0)

    # Store the hybrid threshold as the operational threshold because the deployed score is hybrid.
    selection["operational_hybrid_threshold"] = hybrid_threshold
    selection["operational_ml_weight"] = hybrid_weight

    return BinaryBundleResult(
        name=name,
        estimator=estimator,
        calibrator=calibrator,
        threshold=float(hybrid_threshold),
        calibration_metrics=selection,
        validation_metrics=validation,
        rule_validation_metrics=rule_validation,
        hybrid_validation_metrics=hybrid_validation,
        hybrid_weight_ml=hybrid_weight,
        validation_probabilities=np.asarray(hybrid_val, dtype=float),
        public_probabilities=np.asarray(public_hybrid, dtype=float),
    )


def fit_eta_model(
    frame_train: pd.DataFrame,
    frame_cal: pd.DataFrame,
    frame_val: pd.DataFrame,
    x_train: np.ndarray,
    x_cal: np.ndarray,
    x_val: np.ndarray,
    x_public: np.ndarray,
) -> tuple[HistGradientBoostingRegressor | None, dict[str, Any], np.ndarray]:
    train_mask = frame_train["actual_time_to_shortage_minutes"].notna().to_numpy()
    cal_mask = frame_cal["actual_time_to_shortage_minutes"].notna().to_numpy()
    val_mask = frame_val["actual_time_to_shortage_minutes"].notna().to_numpy()
    if train_mask.sum() < 200:
        return None, {"status": "skipped", "reason": "insufficient positive ETA labels"}, np.full(len(x_public), np.nan)

    y_train = frame_train.loc[train_mask, "actual_time_to_shortage_minutes"].to_numpy(float)
    y_cal = frame_cal.loc[cal_mask, "actual_time_to_shortage_minutes"].to_numpy(float)
    y_val = frame_val.loc[val_mask, "actual_time_to_shortage_minutes"].to_numpy(float)
    model = HistGradientBoostingRegressor(
        loss="absolute_error",
        learning_rate=0.06,
        max_iter=120,
        max_leaf_nodes=31,
        min_samples_leaf=25,
        l2_regularization=1.0,
        early_stopping=True,
        validation_fraction=0.12,
        n_iter_no_change=12,
        random_state=RANDOM_STATE,
    )
    model.fit(x_train[train_mask], y_train)
    val_pred = np.clip(model.predict(x_val[val_mask]), 0.0, 120.0)
    cal_pred = np.clip(model.predict(x_cal[cal_mask]), 0.0, 120.0) if cal_mask.sum() else np.array([])
    metrics = {
        "status": "trained",
        "train_rows": int(train_mask.sum()),
        "calibration_rows": int(cal_mask.sum()),
        "validation_rows": int(val_mask.sum()),
        "validation_mae_minutes": round(float(mean_absolute_error(y_val, val_pred)), 6) if len(y_val) else None,
        "validation_rmse_minutes": round(float(mean_squared_error(y_val, val_pred) ** 0.5), 6) if len(y_val) else None,
        "calibration_mae_minutes": round(float(mean_absolute_error(y_cal, cal_pred)), 6) if len(y_cal) else None,
    }
    return model, metrics, np.clip(model.predict(x_public), 0.0, 120.0)


def fit_service_model(
    frame_train: pd.DataFrame,
    frame_val: pd.DataFrame,
    x_train: np.ndarray,
    x_val: np.ndarray,
    x_public: np.ndarray,
) -> tuple[SGDClassifier | None, dict[str, Any], np.ndarray]:
    def labels(frame: pd.DataFrame) -> pd.Series:
        return frame["affected_service"].astype("string").str.split(":", n=1).str[0]

    y_train_all = labels(frame_train)
    y_val_all = labels(frame_val)
    train_mask = y_train_all.notna().to_numpy()
    val_mask = y_val_all.notna().to_numpy()
    if train_mask.sum() < 200:
        return None, {"status": "skipped", "reason": "insufficient affected-service labels"}, np.full(len(x_public), "unknown", dtype=object)

    y_train = y_train_all[train_mask].astype(str).to_numpy()
    y_val = y_val_all[val_mask].astype(str).to_numpy()
    model = SGDClassifier(
        loss="log_loss",
        penalty="elasticnet",
        alpha=0.0003,
        l1_ratio=0.05,
        class_weight="balanced",
        max_iter=2000,
        tol=1e-4,
        random_state=RANDOM_STATE,
    )
    model.fit(x_train[train_mask], y_train)
    pred = model.predict(x_val[val_mask])
    metrics = {
        "status": "trained",
        "classes": model.classes_.tolist(),
        "train_rows": int(train_mask.sum()),
        "validation_rows": int(val_mask.sum()),
        "validation_accuracy": round(float(accuracy_score(y_val, pred)), 6) if len(y_val) else None,
        "validation_macro_f1": round(float(f1_score(y_val, pred, average="macro", zero_division=0)), 6) if len(y_val) else None,
    }
    return model, metrics, model.predict(x_public)


def fit_anomaly_type_model(
    frame_train: pd.DataFrame,
    frame_val: pd.DataFrame,
    x_train: np.ndarray,
    x_val: np.ndarray,
    x_public: np.ndarray,
) -> tuple[SGDClassifier | None, dict[str, Any], np.ndarray]:
    train_mask = (frame_train["is_unusual"].to_numpy(int) == 1) & frame_train["anomaly_type"].notna().to_numpy()
    val_mask = (frame_val["is_unusual"].to_numpy(int) == 1) & frame_val["anomaly_type"].notna().to_numpy()
    if train_mask.sum() < 500:
        return None, {"status": "skipped", "reason": "insufficient anomaly type labels"}, np.full(len(x_public), "unknown", dtype=object)
    y_train = frame_train.loc[train_mask, "anomaly_type"].astype(str).to_numpy()
    y_val = frame_val.loc[val_mask, "anomaly_type"].astype(str).to_numpy()
    model = SGDClassifier(
        loss="log_loss",
        penalty="elasticnet",
        alpha=0.0004,
        l1_ratio=0.05,
        class_weight="balanced",
        max_iter=2500,
        tol=1e-4,
        random_state=RANDOM_STATE,
    )
    model.fit(x_train[train_mask], y_train)
    pred = model.predict(x_val[val_mask])
    metrics = {
        "status": "trained",
        "classes": model.classes_.tolist(),
        "train_rows": int(train_mask.sum()),
        "validation_rows": int(val_mask.sum()),
        "validation_accuracy": round(float(accuracy_score(y_val, pred)), 6) if len(y_val) else None,
        "validation_macro_f1": round(float(f1_score(y_val, pred, average="macro", zero_division=0)), 6) if len(y_val) else None,
    }
    return model, metrics, model.predict(x_public)


def stakeholder_route(
    anomaly: bool,
    shortage: bool,
    data_issue: bool,
    affected_service: str,
    high_severity: bool,
) -> tuple[str, str]:
    service = affected_service if affected_service in {"shared_cash", "bkash", "nagad", "rocket"} else "unknown"
    if data_issue:
        primary = "data_operations"
        secondary = "area_manager"
    elif shortage and anomaly:
        primary = "area_manager+risk_reviewer"
        secondary = "central_operations" if high_severity else (f"{service}_operations" if service != "shared_cash" else "outlet_operator")
    elif shortage:
        primary = "area_manager"
        secondary = "central_operations" if high_severity else (f"{service}_operations" if service != "shared_cash" else "outlet_operator")
    elif anomaly:
        primary = "risk_reviewer"
        secondary = f"{service}_operations" if service not in {"shared_cash", "unknown"} else "area_manager"
    else:
        primary = "outlet_operator"
        secondary = "none"
    return primary, secondary


def global_importance(
    model: HistGradientBoostingClassifier,
    x_val: np.ndarray,
    y_val: np.ndarray,
    feature_names: list[str],
    max_rows: int = 1500,
) -> list[dict[str, Any]]:
    if len(x_val) > max_rows:
        rng = np.random.default_rng(RANDOM_STATE)
        positives = np.flatnonzero(np.asarray(y_val) == 1)
        negatives = np.flatnonzero(np.asarray(y_val) == 0)
        positive_take = min(len(positives), max_rows // 2)
        negative_take = min(len(negatives), max_rows - positive_take)
        selected = np.concatenate([
            rng.choice(positives, size=positive_take, replace=False) if positive_take else np.array([], dtype=int),
            rng.choice(negatives, size=negative_take, replace=False) if negative_take else np.array([], dtype=int),
        ])
        x_sample = x_val[selected]
        y_sample = np.asarray(y_val)[selected]
    else:
        x_sample = x_val
        y_sample = np.asarray(y_val)
    result = permutation_importance(
        model,
        x_sample,
        y_sample,
        scoring="average_precision",
        n_repeats=1,
        random_state=RANDOM_STATE,
        n_jobs=2,
    )
    order = np.argsort(result.importances_mean)[::-1][:20]
    return [
        {
            "feature": str(feature_names[idx]),
            "importance_mean": round(float(result.importances_mean[idx]), 8),
            "direction": "global_predictive_importance",
        }
        for idx in order
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--max-rows", type=int, default=0, help="Development-only row cap; 0 uses full data.")
    parser.add_argument("--skip-importance", action="store_true")
    args = parser.parse_args()
    root = args.project_root.resolve()

    train_path = root / "data" / "raw" / "train" / "pressure_stress_train_5m.csv.gz"
    public_path = root / "data" / "raw" / "blind_test" / "public" / "pressure_stress_test_5m.csv.gz"
    private_root = root / "data" / "private" / "blind_test_ground_truth"
    if not train_path.exists() or not public_path.exists():
        raise FileNotFoundError("Imported stress train/public files are missing.")

    print("Loading exact 5-minute training and blind-public benchmarks...")
    train_raw = pd.read_csv(train_path, compression="gzip", low_memory=False)
    public_raw = pd.read_csv(public_path, compression="gzip", low_memory=False)
    validate_raw_schema(train_raw, public_raw)
    if args.max_rows and len(train_raw) > args.max_rows:
        episode_ids = train_raw["episode_id"].drop_duplicates().tolist()
        selected: list[str] = []
        running = 0
        counts = train_raw["episode_id"].value_counts()
        for episode_id in episode_ids:
            selected.append(episode_id)
            running += int(counts.get(episode_id, 0))
            if running >= args.max_rows:
                break
        train_raw = train_raw[train_raw["episode_id"].isin(selected)].reset_index(drop=True)
        public_raw = public_raw.head(min(args.max_rows // 2, len(public_raw))).copy()
    print(f"- train rows: {len(train_raw):,}")
    print(f"- blind public rows: {len(public_raw):,}")
    print("- private blind-test labels: not opened")

    train = add_split(engineer_features(train_raw))
    public = engineer_features(public_raw)

    train_part = train[train["_model_split"] == "train"].reset_index(drop=True)
    cal_part = train[train["_model_split"] == "calibration"].reset_index(drop=True)
    val_part = train[train["_model_split"] == "validation"].reset_index(drop=True)

    split_episode_overlap = {
        "train_calibration": len(set(train_part["episode_id"]) & set(cal_part["episode_id"])),
        "train_validation": len(set(train_part["episode_id"]) & set(val_part["episode_id"])),
        "calibration_validation": len(set(cal_part["episode_id"]) & set(val_part["episode_id"])),
    }
    if any(split_episode_overlap.values()):
        raise RuntimeError(f"Episode leakage detected: {split_episode_overlap}")

    print("Fitting one shared preprocessing contract...")
    preprocessor = make_preprocessor()
    x_train = preprocessor.fit_transform(train_part[FEATURE_COLUMNS]).astype(np.float32)
    x_cal = preprocessor.transform(cal_part[FEATURE_COLUMNS]).astype(np.float32)
    x_val = preprocessor.transform(val_part[FEATURE_COLUMNS]).astype(np.float32)
    x_public = preprocessor.transform(public[FEATURE_COLUMNS]).astype(np.float32)
    feature_names = preprocessor.get_feature_names_out().tolist()
    print(f"- transformed feature count: {len(feature_names)}")

    hard_train = train_part["hard_negative_flag"].fillna(0).to_numpy(int) == 1
    hard_cal = cal_part["hard_negative_flag"].fillna(0).to_numpy(int) == 1
    hard_val = val_part["hard_negative_flag"].fillna(0).to_numpy(int) == 1
    context_cols = ["festival_flag", "salary_flag", "remittance_flag", "market_day_flag", "network_recovery_flag"]
    context_cal = cal_part[context_cols].fillna(0).sum(axis=1).to_numpy() > 0
    context_val = val_part[context_cols].fillna(0).sum(axis=1).to_numpy() > 0

    bundles: dict[str, BinaryBundleResult] = {}
    for name, target in TARGETS.items():
        print(f"Training {name} model...")
        bundles[name] = train_binary_task(
            name=name,
            y_train=train_part[target].to_numpy(int),
            y_cal=cal_part[target].to_numpy(int),
            y_val=val_part[target].to_numpy(int),
            x_train=x_train,
            x_cal=x_cal,
            x_val=x_val,
            x_public=x_public,
            cal_frame=cal_part,
            val_frame=val_part,
            public_frame=public,
            hard_train=hard_train,
            hard_cal=hard_cal,
            hard_val=hard_val,
            context_cal=context_cal,
            context_val=context_val,
        )
        metrics = bundles[name].hybrid_validation_metrics
        print(
            f"  validation precision={metrics['precision']:.3f} recall={metrics['recall']:.3f} "
            f"f2={metrics['f2']:.3f} fpr={metrics['false_positive_rate']:.3f}"
        )

    print("Training shortage ETA model...")
    eta_model, eta_metrics, eta_public = fit_eta_model(
        train_part, cal_part, val_part, x_train, x_cal, x_val, x_public
    )

    print("Training affected-service routing helper...")
    service_model, service_metrics, service_public = fit_service_model(
        train_part, val_part, x_train, x_val, x_public
    )

    print("Using deterministic anomaly evidence categories for speed and safety...")
    anomaly_type_model = None
    anomaly_type_metrics = {
        "status": "deterministic_evidence_only",
        "reason": "Exact anomaly-family labeling remains human-reviewed; the model predicts review risk, not a fraud verdict.",
    }
    anomaly_type_public = np.full(len(public), "requires_human_review", dtype=object)

    # Global importance for the two central outputs.
    print("Computing compact permutation feature importance...")
    importance = {
        "anomaly": global_importance(
            bundles["anomaly"].estimator, x_val, val_part[TARGETS["anomaly"]].to_numpy(int), feature_names
        ),
        "shortage_60m": global_importance(
            bundles["shortage_60m"].estimator, x_val, val_part[TARGETS["shortage_60m"]].to_numpy(int), feature_names
        ),
    }

    artifact_dir = root / "artifacts" / "models" / "phase6b"
    prediction_dir = root / "artifacts" / "predictions"
    report_dir = root / "reports" / "model_training"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    prediction_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    binary_payload: dict[str, Any] = {}
    for name, bundle in bundles.items():
        binary_payload[name] = {
            "estimator": bundle.estimator,
            "calibrator": bundle.calibrator,
            "threshold": bundle.threshold,
            "hybrid_weight_ml": bundle.hybrid_weight_ml,
            "hybrid_weight_rule": 1.0 - bundle.hybrid_weight_ml,
        }

    model_bundle = {
        "model_name": "superagent-sentinel-phase6b",
        "model_version": "phase6b-1.0.0",
        "created_at": utc_now(),
        "preprocessor": preprocessor,
        "feature_columns": FEATURE_COLUMNS,
        "transformed_feature_names": feature_names,
        "binary_models": binary_payload,
        "eta_model": eta_model,
        "affected_service_model": service_model,
        "anomaly_type_model": anomaly_type_model,
        "safety_boundary": (
            "Advisory scoring only. Stakeholder routing is deterministic and human action is required. "
            "No fund movement, freeze, block, or fraud verdict is authorized."
        ),
    }
    bundle_path = artifact_dir / "phase6b_model_bundle.joblib"
    joblib.dump(model_bundle, bundle_path, compress=1)

    # Public blind predictions without touching ground truth.
    anomaly_p = np.clip(bundles["anomaly"].public_probabilities, 0, 1)
    shortage_30 = np.clip(bundles["shortage_30m"].public_probabilities, 0, 1)
    shortage_60 = np.maximum(shortage_30, np.clip(bundles["shortage_60m"].public_probabilities, 0, 1))
    shortage_120 = np.maximum(shortage_60, np.clip(bundles["shortage_120m"].public_probabilities, 0, 1))

    data_issue = (
        (public["data_quality_score"].to_numpy(float) < 0.60)
        | (public["missing_ratio"].to_numpy(float) >= 0.20)
        | (public["feed_age_seconds"].to_numpy(float) > 900)
        | (public["reconciliation_difference"].to_numpy(float) > 25000)
    )
    anomaly_flag = anomaly_p >= bundles["anomaly"].threshold
    shortage_flag = shortage_60 >= bundles["shortage_60m"].threshold
    high_severity = (np.maximum(anomaly_p, shortage_60) >= 0.85) | (
        shortage_30 >= bundles["shortage_30m"].threshold
    )

    predicted_service = np.asarray(service_public, dtype=object)
    predicted_service = np.where(shortage_120 >= bundles["shortage_120m"].threshold, predicted_service, "none")
    predicted_type = np.asarray(anomaly_type_public, dtype=object)
    predicted_type = np.where(anomaly_flag, predicted_type, "normal")

    routes = [
        stakeholder_route(bool(a), bool(s), bool(d), str(service), bool(high))
        for a, s, d, service, high in zip(anomaly_flag, shortage_flag, data_issue, predicted_service, high_severity)
    ]
    primary = [item[0] for item in routes]
    secondary = [item[1] for item in routes]

    predictions = pd.DataFrame(
        {
            "episode_id": public["episode_id"].astype(str),
            "window_id": public["window_id"].astype(str),
            "timestamp": public["timestamp"].astype(str),
            "anomaly_probability": np.round(anomaly_p, 8),
            "anomaly_requires_review": anomaly_flag.astype(int),
            "predicted_anomaly_type": predicted_type,
            "shortage_probability_30m": np.round(shortage_30, 8),
            "shortage_probability_60m": np.round(shortage_60, 8),
            "shortage_probability_120m": np.round(shortage_120, 8),
            "shortage_within_30m_pred": (shortage_30 >= bundles["shortage_30m"].threshold).astype(int),
            "shortage_within_60m_pred": shortage_flag.astype(int),
            "shortage_within_120m_pred": (shortage_120 >= bundles["shortage_120m"].threshold).astype(int),
            "estimated_time_to_shortage_minutes": np.round(eta_public, 3),
            "predicted_affected_service": predicted_service,
            "data_verification_required": data_issue.astype(int),
            "primary_stakeholder": primary,
            "secondary_stakeholder": secondary,
            "human_review_required": (anomaly_flag | shortage_flag | data_issue).astype(int),
            "model_version": "phase6b-1.0.0",
        }
    )
    prediction_path = prediction_dir / "phase6b_blind_public_predictions.csv.gz"
    predictions.to_csv(prediction_path, index=False, compression="gzip")

    validation_metrics = {
        name: {
            "calibration_threshold_selection": bundle.calibration_metrics,
            "ml_validation": bundle.validation_metrics,
            "rule_validation": bundle.rule_validation_metrics,
            "hybrid_validation": bundle.hybrid_validation_metrics,
            "operational_threshold": bundle.threshold,
            "hybrid_weight_ml": bundle.hybrid_weight_ml,
        }
        for name, bundle in bundles.items()
    }

    summary = {
        "model_name": "superagent-sentinel-phase6b",
        "model_version": "phase6b-1.0.0",
        "created_at": utc_now(),
        "training_data": {
            "path": str(train_path),
            "sha256": sha256_file(train_path),
            "rows": int(len(train)),
            "episodes": int(train["episode_id"].nunique()),
            "split_rows": {
                "train": int(len(train_part)),
                "calibration": int(len(cal_part)),
                "validation": int(len(val_part)),
            },
            "split_episodes": {
                "train": int(train_part["episode_id"].nunique()),
                "calibration": int(cal_part["episode_id"].nunique()),
                "validation": int(val_part["episode_id"].nunique()),
            },
            "episode_overlap": split_episode_overlap,
        },
        "blind_public": {
            "path": str(public_path),
            "sha256": sha256_file(public_path),
            "rows": int(len(public)),
            "prediction_path": str(prediction_path),
            "prediction_sha256": sha256_file(prediction_path),
        },
        "blind_private_policy": {
            "private_root_exists": private_root.exists(),
            "private_files_opened": 0,
            "private_label_values_inspected": False,
            "evaluation_allowed_only_after_model_freeze": True,
        },
        "feature_contract": {
            "input_features": FEATURE_COLUMNS,
            "transformed_feature_count": int(len(feature_names)),
            "forbidden_leakage_features": sorted(FORBIDDEN_TRAINING_FEATURES),
            "forbidden_prefixes": list(FORBIDDEN_TRAINING_FEATURE_PREFIXES),
        },
        "validation_metrics": validation_metrics,
        "eta_model": eta_metrics,
        "affected_service_model": service_metrics,
        "anomaly_type_model": anomaly_type_metrics,
        "feature_importance": importance,
        "public_prediction_counts": {
            "human_review_required": int(predictions["human_review_required"].sum()),
            "anomaly_review": int(predictions["anomaly_requires_review"].sum()),
            "shortage_60m": int(predictions["shortage_within_60m_pred"].sum()),
            "data_verification": int(predictions["data_verification_required"].sum()),
        },
        "safety": {
            "ai_final_decision_maker": False,
            "stakeholder_routing": "deterministic_from_validated_model_outputs_and_scope_policy",
            "forbidden_actions": [
                "automatic_fund_movement",
                "automatic_provider_transfer",
                "automatic_account_freeze",
                "automatic_customer_block",
                "fraud_verdict",
            ],
        },
    }
    metrics_path = report_dir / "phase6b_metrics.json"
    json_write(metrics_path, summary)

    feature_contract_path = report_dir / "phase6b_feature_contract.json"
    json_write(
        feature_contract_path,
        {
            "version": "phase6b-1.0.0",
            "raw_required_columns": ID_COLUMNS + CATEGORICAL_COLUMNS + BASE_NUMERIC_COLUMNS,
            "categorical_features": CATEGORICAL_COLUMNS,
            "numeric_features": NUMERIC_COLUMNS,
            "derived_features": DERIVED_NUMERIC_COLUMNS,
            "output_validation": {
                "probability_range": [0.0, 1.0],
                "shortage_horizon_monotonicity": "p30 <= p60 <= p120 enforced after prediction",
                "eta_range_minutes": [0.0, 120.0],
                "human_review": "required for model threshold, data issue, or hybrid high-risk output",
            },
        },
    )

    freeze_manifest = {
        "freeze_id": "phase6b-1.0.0",
        "frozen_at": utc_now(),
        "model_bundle": {"path": str(bundle_path), "sha256": sha256_file(bundle_path)},
        "metrics": {"path": str(metrics_path), "sha256": sha256_file(metrics_path)},
        "feature_contract": {"path": str(feature_contract_path), "sha256": sha256_file(feature_contract_path)},
        "blind_public_predictions": {"path": str(prediction_path), "sha256": sha256_file(prediction_path)},
        "thresholds": {name: bundle.threshold for name, bundle in bundles.items()},
        "private_ground_truth_used": False,
        "next_step": "Phase 6C may evaluate this frozen prediction file against private ground truth without retraining or retuning.",
    }
    freeze_path = report_dir / "phase6b_freeze_manifest.json"
    json_write(freeze_path, freeze_manifest)

    lines = [
        "# Phase 6B Model Card",
        "",
        "- Model version: `phase6b-1.0.0`",
        f"- Exact 5-minute training rows: `{len(train):,}`",
        f"- Episode-separated train/calibration/validation: `{len(train_part):,}` / `{len(cal_part):,}` / `{len(val_part):,}`",
        f"- Blind public rows predicted: `{len(public):,}`",
        "- Private ground-truth values opened: `No`",
        "",
        "## Validation summary",
        "",
        "| Task | Precision | Recall | F2 | PR-AUC | FPR | Hard-negative FPR |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, bundle in bundles.items():
        m = bundle.hybrid_validation_metrics
        lines.append(
            f"| {name} | {m['precision']:.3f} | {m['recall']:.3f} | {m['f2']:.3f} | "
            f"{(m.get('pr_auc') or 0):.3f} | {m['false_positive_rate']:.3f} | "
            f"{(m.get('hard_negative_fpr') or 0):.3f} |"
        )
    lines.extend([
        "",
        "## Design",
        "",
        "- CPU-friendly histogram gradient boosting for anomaly and shortage horizons.",
        "- Episode-level split prevents adjacent-window leakage.",
        "- Separate calibration split chooses thresholds without touching validation.",
        "- Hard-negative rush windows receive extra training weight.",
        "- Hybrid score combines calibrated ML with deterministic operational rules.",
        "- Data-quality issues use deterministic verification rules.",
        "- Stakeholder routing is deterministic and human-controlled.",
        "",
        "## Safety",
        "",
        "AI is not the final decision maker. The system cannot move funds, freeze/block, or issue a fraud verdict.",
        "",
    ])
    (report_dir / "PHASE6B_MODEL_CARD.md").write_text("\n".join(lines), encoding="utf-8")

    print("PHASE 6B TRAINING PASSED")
    print(f"- model bundle: {bundle_path}")
    print(f"- metrics: {metrics_path}")
    print(f"- freeze manifest: {freeze_path}")
    print(f"- blind public predictions: {prediction_path}")
    print("- private ground-truth values inspected: NO")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"PHASE 6B TRAINING FAILED: {exc}", file=sys.stderr)
        raise