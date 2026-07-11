from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    fbeta_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    recall_score,
    roc_auc_score,
)

KEYS = ["episode_id", "window_id", "timestamp"]

PROBABILITY_COLUMNS = [
    "anomaly_probability",
    "shortage_probability_30m",
    "shortage_probability_60m",
    "shortage_probability_120m",
]

PREDICTION_COLUMNS = [
    *KEYS,
    "anomaly_probability",
    "anomaly_requires_review",
    "predicted_anomaly_type",
    "shortage_probability_30m",
    "shortage_probability_60m",
    "shortage_probability_120m",
    "shortage_within_30m_pred",
    "shortage_within_60m_pred",
    "shortage_within_120m_pred",
    "estimated_time_to_shortage_minutes",
    "predicted_affected_service",
    "data_verification_required",
    "primary_stakeholder",
    "secondary_stakeholder",
    "human_review_required",
    "model_version",
]

PRIVATE_COLUMNS = [
    *KEYS,
    "is_unusual",
    "scenario_family",
    "anomaly_type",
    "severity",
    "hard_negative_flag",
    "data_quality_issue_flag",
    "label_confidence",
    "shortage_within_30m",
    "shortage_within_60m",
    "shortage_within_120m",
    "actual_time_to_shortage_minutes",
    "affected_service",
]

PUBLIC_CONTEXT_COLUMNS = [
    *KEYS,
    "festival_flag",
    "salary_flag",
    "remittance_flag",
    "market_day_flag",
    "network_recovery_flag",
    "agent_profile",
    "location_type",
    "provider_mix_shift",
    "data_quality_score",
    "feed_age_seconds",
    "reconciliation_difference",
]

ALLOWED_SERVICES = {"none", "unknown", "shared_cash", "bkash", "nagad", "rocket"}
ALLOWED_PRIMARY_ROUTES = {
    "data_operations",
    "area_manager+risk_reviewer",
    "area_manager",
    "risk_reviewer",
    "outlet_operator",
}
ALLOWED_SECONDARY_ROUTES = {
    "area_manager",
    "central_operations",
    "outlet_operator",
    "bkash_operations",
    "nagad_operations",
    "rocket_operations",
    "none",
    "unknown_operations",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def to_builtin(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): to_builtin(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_builtin(v) for v in value]
    if isinstance(value, tuple):
        return [to_builtin(v) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def ece_score(y_true: np.ndarray, probabilities: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = len(y_true)
    if total == 0:
        return float("nan")
    ece = 0.0
    for index in range(bins):
        low, high = edges[index], edges[index + 1]
        if index == bins - 1:
            mask = (probabilities >= low) & (probabilities <= high)
        else:
            mask = (probabilities >= low) & (probabilities < high)
        count = int(mask.sum())
        if count == 0:
            continue
        confidence = float(probabilities[mask].mean())
        accuracy = float(y_true[mask].mean())
        ece += (count / total) * abs(confidence - accuracy)
    return float(ece)


def binary_metrics(
    y_true: pd.Series | np.ndarray,
    probability: pd.Series | np.ndarray,
    prediction: pd.Series | np.ndarray,
) -> dict[str, Any]:
    truth = np.asarray(y_true, dtype=int)
    prob = np.asarray(probability, dtype=float)
    pred = np.asarray(prediction, dtype=int)
    tn, fp, fn, tp = confusion_matrix(truth, pred, labels=[0, 1]).ravel()
    negative = tn + fp
    positive = tp + fn
    result: dict[str, Any] = {
        "rows": int(len(truth)),
        "positive_support": int(positive),
        "negative_support": int(negative),
        "prevalence": float(truth.mean()) if len(truth) else None,
        "predicted_positive_rate": float(pred.mean()) if len(pred) else None,
        "true_negative": int(tn),
        "false_positive": int(fp),
        "false_negative": int(fn),
        "true_positive": int(tp),
        "precision": float(precision_score(truth, pred, zero_division=0)),
        "recall": float(recall_score(truth, pred, zero_division=0)),
        "f1": float(f1_score(truth, pred, zero_division=0)),
        "f2": float(fbeta_score(truth, pred, beta=2, zero_division=0)),
        "accuracy": float(accuracy_score(truth, pred)),
        "balanced_accuracy": (
            float(balanced_accuracy_score(truth, pred))
            if len(np.unique(truth)) > 1
            else float(accuracy_score(truth, pred))
        ),
        "false_positive_rate": float(fp / negative) if negative else None,
        "false_negative_rate": float(fn / positive) if positive else None,
        "specificity": float(tn / negative) if negative else None,
        "brier_score": float(brier_score_loss(truth, prob)),
        "expected_calibration_error_10_bin": ece_score(truth, prob, bins=10),
    }
    if len(np.unique(truth)) > 1:
        result["pr_auc"] = float(average_precision_score(truth, prob))
        result["roc_auc"] = float(roc_auc_score(truth, prob))
    else:
        result["pr_auc"] = None
        result["roc_auc"] = None
    return result


def safe_binary_subset(
    frame: pd.DataFrame,
    mask: pd.Series | np.ndarray,
    truth_column: str,
    probability_column: str,
    prediction_column: str,
) -> dict[str, Any]:
    subset = frame.loc[np.asarray(mask, dtype=bool)]
    if subset.empty:
        return {"rows": 0}
    return binary_metrics(
        subset[truth_column],
        subset[probability_column],
        subset[prediction_column],
    )


def normalize_service(value: Any) -> str:
    if pd.isna(value):
        return "none"
    service = str(value).split(":", 1)[0].strip().lower()
    return service if service in {"shared_cash", "bkash", "nagad", "rocket"} else "none"


def expected_route(row: pd.Series) -> tuple[str, str]:
    anomaly = bool(int(row["is_unusual"]))
    shortage = bool(int(row["shortage_within_60m"]))
    data_issue = bool(int(row["data_quality_issue_flag"]))
    severity = str(row.get("severity", "")).lower()
    high = severity == "high"
    service = normalize_service(row.get("affected_service"))

    if data_issue:
        return "data_operations", "area_manager"
    if shortage and anomaly:
        secondary = "central_operations" if high else (
            "outlet_operator" if service == "shared_cash" else f"{service}_operations"
        )
        if service == "none" and not high:
            secondary = "area_manager"
        return "area_manager+risk_reviewer", secondary
    if shortage:
        secondary = "central_operations" if high else (
            "outlet_operator" if service == "shared_cash" else f"{service}_operations"
        )
        if service == "none" and not high:
            secondary = "area_manager"
        return "area_manager", secondary
    if anomaly:
        secondary = f"{service}_operations" if service not in {"none", "shared_cash"} else "area_manager"
        return "risk_reviewer", secondary
    return "outlet_operator", "none"


def context_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    contexts = {
        "all": np.ones(len(frame), dtype=bool),
        "festival": frame["festival_flag"].astype(int).eq(1),
        "salary": frame["salary_flag"].astype(int).eq(1),
        "remittance": frame["remittance_flag"].astype(int).eq(1),
        "market_day": frame["market_day_flag"].astype(int).eq(1),
        "network_recovery": frame["network_recovery_flag"].astype(int).eq(1),
        "any_rush_context": (
            frame[["festival_flag", "salary_flag", "remittance_flag", "market_day_flag"]]
            .astype(int)
            .sum(axis=1)
            .gt(0)
        ),
        "hard_negative": frame["hard_negative_flag"].astype(int).eq(1),
        "data_quality_issue": frame["data_quality_issue_flag"].astype(int).eq(1),
        "healthy_data": frame["data_quality_issue_flag"].astype(int).eq(0),
    }
    rows: list[dict[str, Any]] = []
    for context, mask in contexts.items():
        subset = frame.loc[np.asarray(mask, dtype=bool)]
        if subset.empty:
            continue
        anomaly = binary_metrics(
            subset["is_unusual"],
            subset["anomaly_probability"],
            subset["anomaly_requires_review"],
        )
        shortage = binary_metrics(
            subset["shortage_within_60m"],
            subset["shortage_probability_60m"],
            subset["shortage_within_60m_pred"],
        )
        rows.append(
            {
                "context": context,
                "rows": len(subset),
                "anomaly_prevalence": anomaly["prevalence"],
                "anomaly_precision": anomaly["precision"],
                "anomaly_recall": anomaly["recall"],
                "anomaly_fpr": anomaly["false_positive_rate"],
                "shortage_60m_prevalence": shortage["prevalence"],
                "shortage_60m_precision": shortage["precision"],
                "shortage_60m_recall": shortage["recall"],
                "shortage_60m_fpr": shortage["false_positive_rate"],
                "review_rate": float(subset["human_review_required"].mean()),
            }
        )
    return pd.DataFrame(rows)


def group_metrics(
    frame: pd.DataFrame,
    group_column: str,
    truth_column: str,
    probability_column: str,
    prediction_column: str,
    min_rows: int = 20,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for value, subset in frame.groupby(group_column, dropna=False):
        if len(subset) < min_rows:
            continue
        metrics = binary_metrics(
            subset[truth_column],
            subset[probability_column],
            subset[prediction_column],
        )
        rows.append(
            {
                group_column: "missing" if pd.isna(value) else str(value),
                **metrics,
            }
        )
    return pd.DataFrame(rows)


def validation_reference(metrics_payload: dict[str, Any], name: str) -> dict[str, Any]:
    item = metrics_payload.get("validation_metrics", {}).get(name, {})
    for key in ("hybrid_validation", "ml_validation"):
        candidate = item.get(key)
        if isinstance(candidate, dict):
            return candidate
    return {}


def retention_check(blind: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    for metric in ("precision", "recall", "f2", "pr_auc"):
        blind_value = blind.get(metric)
        validation_value = validation.get(metric)
        if blind_value is None or validation_value in (None, 0):
            checks[metric] = None
        else:
            checks[metric] = {
                "blind": blind_value,
                "validation": validation_value,
                "retention_ratio": blind_value / validation_value,
                "advisory_status": "stable" if blind_value >= 0.70 * validation_value else "degraded",
            }
    blind_fpr = blind.get("false_positive_rate")
    validation_fpr = validation.get("false_positive_rate")
    if blind_fpr is not None and validation_fpr is not None:
        allowance = max(0.05, 2.5 * validation_fpr)
        checks["false_positive_rate"] = {
            "blind": blind_fpr,
            "validation": validation_fpr,
            "advisory_limit": allowance,
            "advisory_status": "stable" if blind_fpr <= allowance else "degraded",
        }
    return checks


def format_float(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args()

    root = args.project_root.resolve()
    prediction_path = root / "artifacts" / "predictions" / "phase6b_blind_public_predictions.csv.gz"
    public_path = root / "data" / "raw" / "blind_test" / "public" / "pressure_stress_test_5m.csv.gz"
    private_path = root / "data" / "private" / "blind_test_ground_truth" / "pressure_stress_labels_private.csv.gz"
    freeze_path = root / "reports" / "model_training" / "phase6b_freeze_manifest.json"
    validation_metrics_path = root / "reports" / "model_training" / "phase6b_metrics.json"
    bundle_path = root / "artifacts" / "models" / "phase6b" / "phase6b_model_bundle.joblib"
    feature_contract_path = root / "reports" / "model_training" / "phase6b_feature_contract.json"
    report_dir = root / "reports" / "model_evaluation"
    report_dir.mkdir(parents=True, exist_ok=True)

    required_paths = [
        prediction_path,
        public_path,
        private_path,
        freeze_path,
        validation_metrics_path,
        bundle_path,
        feature_contract_path,
    ]
    for path in required_paths:
        if not path.exists():
            raise FileNotFoundError(f"Required Phase 6C input is missing: {path}")

    print("Verifying frozen Phase 6B artifacts before opening private labels...")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8-sig"))
    validation_metrics_payload = json.loads(validation_metrics_path.read_text(encoding="utf-8-sig"))

    expected_hashes = {
        "model_bundle": freeze["model_bundle"]["sha256"],
        "metrics": freeze["metrics"]["sha256"],
        "feature_contract": freeze["feature_contract"]["sha256"],
        "blind_public_predictions": freeze["blind_public_predictions"]["sha256"],
    }
    actual_hashes = {
        "model_bundle": sha256_file(bundle_path),
        "metrics": sha256_file(validation_metrics_path),
        "feature_contract": sha256_file(feature_contract_path),
        "blind_public_predictions": sha256_file(prediction_path),
    }
    hash_match = {name: actual_hashes[name] == expected_hashes[name] for name in expected_hashes}
    if not all(hash_match.values()):
        raise ValueError(f"Frozen artifact hash mismatch: {hash_match}")
    if freeze.get("private_ground_truth_used") is not False:
        raise ValueError("Freeze manifest does not prove private ground truth was excluded in Phase 6B.")

    print("Frozen hashes verified. Opening private labels for one-time evaluation only...")
    predictions = pd.read_csv(prediction_path)
    public = pd.read_csv(public_path, usecols=lambda name: name in PUBLIC_CONTEXT_COLUMNS)
    private = pd.read_csv(private_path, usecols=lambda name: name in PRIVATE_COLUMNS)

    missing_prediction_columns = sorted(set(PREDICTION_COLUMNS) - set(predictions.columns))
    missing_private_columns = sorted(set(PRIVATE_COLUMNS) - set(private.columns))
    missing_public_columns = sorted(set(PUBLIC_CONTEXT_COLUMNS) - set(public.columns))
    if missing_prediction_columns:
        raise ValueError(f"Prediction file is missing columns: {missing_prediction_columns}")
    if missing_private_columns:
        raise ValueError(f"Private labels are missing columns: {missing_private_columns}")
    if missing_public_columns:
        raise ValueError(f"Public benchmark is missing columns: {missing_public_columns}")

    for frame in (predictions, public, private):
        for key in KEYS:
            frame[key] = frame[key].astype(str)

    duplicate_counts = {
        "predictions": int(predictions.duplicated(KEYS).sum()),
        "public": int(public.duplicated(KEYS).sum()),
        "private": int(private.duplicated(KEYS).sum()),
    }
    if any(duplicate_counts.values()):
        raise ValueError(f"Duplicate evaluation keys detected: {duplicate_counts}")

    merged = public.merge(private, on=KEYS, how="outer", validate="one_to_one", indicator="_public_private")
    public_private_alignment = {
        str(key): int(value)
        for key, value in merged["_public_private"].value_counts(dropna=False).to_dict().items()
        if int(value) > 0
    }
    if set(public_private_alignment) != {"both"}:
        raise ValueError(f"Public/private key alignment failed: {public_private_alignment}")
    merged = merged.drop(columns="_public_private")

    merged = merged.merge(
        predictions,
        on=KEYS,
        how="outer",
        validate="one_to_one",
        indicator="_prediction_join",
    )
    prediction_alignment = {
        str(key): int(value)
        for key, value in merged["_prediction_join"].value_counts(dropna=False).to_dict().items()
        if int(value) > 0
    }
    if set(prediction_alignment) != {"both"}:
        raise ValueError(f"Prediction/private key alignment failed: {prediction_alignment}")
    merged = merged.drop(columns="_prediction_join")

    if len(merged) != len(private):
        raise ValueError("Evaluation row count changed after one-to-one joins.")

    for column in PROBABILITY_COLUMNS:
        values = pd.to_numeric(merged[column], errors="coerce")
        if values.isna().any() or ((values < 0) | (values > 1)).any():
            raise ValueError(f"Invalid probability values in {column}")
        merged[column] = values

    monotonic_violations = int(
        (
            (merged["shortage_probability_30m"] > merged["shortage_probability_60m"] + 1e-12)
            | (merged["shortage_probability_60m"] > merged["shortage_probability_120m"] + 1e-12)
        ).sum()
    )
    if monotonic_violations:
        raise ValueError(f"Shortage probability monotonicity violations: {monotonic_violations}")

    eta = pd.to_numeric(merged["estimated_time_to_shortage_minutes"], errors="coerce")
    if eta.isna().any() or ((eta < 0) | (eta > 120)).any():
        raise ValueError("Estimated shortage ETA contains missing or out-of-range values.")
    merged["estimated_time_to_shortage_minutes"] = eta

    binary_prediction_columns = [
        "anomaly_requires_review",
        "shortage_within_30m_pred",
        "shortage_within_60m_pred",
        "shortage_within_120m_pred",
        "data_verification_required",
        "human_review_required",
    ]
    for column in binary_prediction_columns:
        values = pd.to_numeric(merged[column], errors="coerce")
        if values.isna().any() or not set(values.unique()).issubset({0, 1}):
            raise ValueError(f"Invalid binary prediction column: {column}")
        merged[column] = values.astype(int)

    service_values = set(merged["predicted_affected_service"].fillna("none").astype(str).unique())
    invalid_services = sorted(service_values - ALLOWED_SERVICES)
    if invalid_services:
        raise ValueError(f"Invalid predicted affected services: {invalid_services}")

    invalid_primary = sorted(set(merged["primary_stakeholder"].astype(str).unique()) - ALLOWED_PRIMARY_ROUTES)
    invalid_secondary = sorted(set(merged["secondary_stakeholder"].astype(str).unique()) - ALLOWED_SECONDARY_ROUTES)
    if invalid_primary or invalid_secondary:
        raise ValueError(
            f"Invalid stakeholder routes. primary={invalid_primary}, secondary={invalid_secondary}"
        )

    model_versions = sorted(merged["model_version"].astype(str).unique())
    if model_versions != ["phase6b-1.0.0"]:
        raise ValueError(f"Unexpected prediction model versions: {model_versions}")

    print("Computing blind-test metrics without retraining or retuning...")
    tasks = {
        "anomaly": (
            "is_unusual",
            "anomaly_probability",
            "anomaly_requires_review",
        ),
        "shortage_30m": (
            "shortage_within_30m",
            "shortage_probability_30m",
            "shortage_within_30m_pred",
        ),
        "shortage_60m": (
            "shortage_within_60m",
            "shortage_probability_60m",
            "shortage_within_60m_pred",
        ),
        "shortage_120m": (
            "shortage_within_120m",
            "shortage_probability_120m",
            "shortage_within_120m_pred",
        ),
        "data_quality_verification": (
            "data_quality_issue_flag",
            "data_quality_score",
            "data_verification_required",
        ),
    }

    metrics: dict[str, Any] = {}
    for name, (truth_column, probability_column, prediction_column) in tasks.items():
        if name == "data_quality_verification":
            # Convert high quality score into a data-issue probability for calibration reporting.
            issue_probability = (1.0 - pd.to_numeric(merged[probability_column], errors="coerce")).clip(0, 1)
            metrics[name] = binary_metrics(
                merged[truth_column],
                issue_probability,
                merged[prediction_column],
            )
        else:
            metrics[name] = binary_metrics(
                merged[truth_column],
                merged[probability_column],
                merged[prediction_column],
            )

    actual_eta = pd.to_numeric(merged["actual_time_to_shortage_minutes"], errors="coerce")
    eta_mask = actual_eta.notna() & merged["shortage_within_120m"].astype(int).eq(1)
    if eta_mask.any():
        eta_abs = (
            merged.loc[eta_mask, "estimated_time_to_shortage_minutes"]
            - actual_eta.loc[eta_mask]
        ).abs()
        eta_metrics = {
            "rows": int(eta_mask.sum()),
            "mae_minutes": float(mean_absolute_error(
                actual_eta.loc[eta_mask],
                merged.loc[eta_mask, "estimated_time_to_shortage_minutes"],
            )),
            "rmse_minutes": float(math.sqrt(mean_squared_error(
                actual_eta.loc[eta_mask],
                merged.loc[eta_mask, "estimated_time_to_shortage_minutes"],
            ))),
            "median_absolute_error_minutes": float(eta_abs.median()),
            "within_15_minutes_rate": float((eta_abs <= 15).mean()),
            "within_30_minutes_rate": float((eta_abs <= 30).mean()),
        }
    else:
        eta_metrics = {"rows": 0}

    true_service = merged["affected_service"].map(normalize_service)
    pred_service = merged["predicted_affected_service"].map(normalize_service)
    service_mask = merged["shortage_within_120m"].astype(int).eq(1) & true_service.ne("none")
    service_accuracy = (
        float(accuracy_score(true_service.loc[service_mask], pred_service.loc[service_mask]))
        if service_mask.any()
        else None
    )
    service_rows = []
    for service in ["shared_cash", "bkash", "nagad", "rocket"]:
        actual_mask = service_mask & true_service.eq(service)
        service_rows.append(
            {
                "service": service,
                "actual_shortage_rows": int(actual_mask.sum()),
                "correct_service_predictions": int(
                    (pred_service.loc[actual_mask] == service).sum()
                ) if actual_mask.any() else 0,
                "service_recall": float(
                    (pred_service.loc[actual_mask] == service).mean()
                ) if actual_mask.any() else None,
                "shortage_120m_recall": float(
                    merged.loc[actual_mask, "shortage_within_120m_pred"].mean()
                ) if actual_mask.any() else None,
            }
        )
    service_df = pd.DataFrame(service_rows)

    anomaly_type_mask = merged["is_unusual"].astype(int).eq(1)
    anomaly_type_accuracy = (
        float(accuracy_score(
            merged.loc[anomaly_type_mask, "anomaly_type"].fillna("unknown").astype(str),
            merged.loc[anomaly_type_mask, "predicted_anomaly_type"].fillna("unknown").astype(str),
        ))
        if anomaly_type_mask.any()
        else None
    )

    expected_routes = merged.apply(expected_route, axis=1, result_type="expand")
    expected_routes.columns = ["expected_primary_stakeholder", "expected_secondary_stakeholder"]
    merged = pd.concat([merged, expected_routes], axis=1)
    primary_route_accuracy = float(
        (merged["primary_stakeholder"] == merged["expected_primary_stakeholder"]).mean()
    )
    secondary_route_accuracy = float(
        (merged["secondary_stakeholder"] == merged["expected_secondary_stakeholder"]).mean()
    )
    exact_route_accuracy = float(
        (
            (merged["primary_stakeholder"] == merged["expected_primary_stakeholder"])
            & (merged["secondary_stakeholder"] == merged["expected_secondary_stakeholder"])
        ).mean()
    )

    expected_review = (
        merged["is_unusual"].astype(int).eq(1)
        | merged["shortage_within_60m"].astype(int).eq(1)
        | merged["data_quality_issue_flag"].astype(int).eq(1)
    ).astype(int)
    human_review_metrics = binary_metrics(
        expected_review,
        merged[
            ["anomaly_probability", "shortage_probability_60m"]
        ].max(axis=1).where(
            merged["data_verification_required"].eq(0),
            1.0,
        ),
        merged["human_review_required"],
    )

    context_df = context_metrics(merged)
    scenario_anomaly_df = group_metrics(
        merged,
        "scenario_family",
        "is_unusual",
        "anomaly_probability",
        "anomaly_requires_review",
    )
    scenario_shortage_df = group_metrics(
        merged,
        "scenario_family",
        "shortage_within_60m",
        "shortage_probability_60m",
        "shortage_within_60m_pred",
    )
    anomaly_type_df = group_metrics(
        merged,
        "anomaly_type",
        "is_unusual",
        "anomaly_probability",
        "anomaly_requires_review",
        min_rows=5,
    )

    route_confusion = pd.crosstab(
        merged["expected_primary_stakeholder"],
        merged["primary_stakeholder"],
        dropna=False,
    ).reset_index()

    validation_retention = {
        name: retention_check(
            metrics[name],
            validation_reference(validation_metrics_payload, name),
        )
        for name in ("anomaly", "shortage_30m", "shortage_60m", "shortage_120m")
    }

    integrity = {
        "evaluated_at": utc_now(),
        "prediction_rows": int(len(predictions)),
        "public_rows": int(len(public)),
        "private_rows": int(len(private)),
        "joined_rows": int(len(merged)),
        "duplicate_key_counts": duplicate_counts,
        "public_private_alignment": {str(k): int(v) for k, v in public_private_alignment.items()},
        "prediction_alignment": {str(k): int(v) for k, v in prediction_alignment.items()},
        "frozen_hash_match": hash_match,
        "probability_ranges_valid": True,
        "shortage_monotonicity_violations": monotonic_violations,
        "eta_range_valid": True,
        "model_versions": model_versions,
        "retraining_performed": False,
        "threshold_retuning_performed": False,
        "private_labels_opened_only_after_freeze_verification": True,
    }

    evaluation = {
        "evaluation_name": "phase6c-frozen-blind-test",
        "evaluated_at": utc_now(),
        "integrity": integrity,
        "tasks": metrics,
        "eta": eta_metrics,
        "affected_service": {
            "evaluated_rows": int(service_mask.sum()),
            "accuracy": service_accuracy,
            "by_service": service_rows,
        },
        "anomaly_type": {
            "evaluated_rows": int(anomaly_type_mask.sum()),
            "accuracy": anomaly_type_accuracy,
        },
        "human_review": human_review_metrics,
        "stakeholder_routing": {
            "primary_accuracy": primary_route_accuracy,
            "secondary_accuracy": secondary_route_accuracy,
            "exact_route_accuracy": exact_route_accuracy,
            "policy": "deterministic, scope-aware, human-controlled",
        },
        "validation_to_blind_retention": validation_retention,
        "safety": {
            "ai_final_decision_maker": False,
            "automatic_money_movement": False,
            "automatic_provider_transfer": False,
            "automatic_freeze_or_block": False,
            "fraud_verdict": False,
            "human_review_required_for_flagged_outputs": True,
        },
        "limitations": [
            "This is a synthetic blind-test evaluation, not a real financial production certification.",
            "Private labels were used only after model, feature contract, thresholds, and prediction hashes were frozen.",
            "No model retraining or threshold retuning was performed in Phase 6C.",
            "Operational rollout still requires real-data monitoring, drift checks, privacy review, and human governance.",
        ],
    }
    evaluation = to_builtin(evaluation)

    metrics_path = report_dir / "phase6c_blind_test_metrics.json"
    integrity_path = report_dir / "phase6c_integrity.json"
    write_json(metrics_path, evaluation)
    write_json(integrity_path, integrity)

    context_df.to_csv(report_dir / "phase6c_context_metrics.csv", index=False)
    scenario_anomaly_df.to_csv(report_dir / "phase6c_scenario_anomaly_metrics.csv", index=False)
    scenario_shortage_df.to_csv(report_dir / "phase6c_scenario_shortage60_metrics.csv", index=False)
    anomaly_type_df.to_csv(report_dir / "phase6c_anomaly_type_metrics.csv", index=False)
    service_df.to_csv(report_dir / "phase6c_service_metrics.csv", index=False)
    route_confusion.to_csv(report_dir / "phase6c_primary_route_confusion.csv", index=False)

    report_lines = [
        "# Phase 6C Frozen Blind-Test Evaluation",
        "",
        f"- Evaluation time: `{evaluation['evaluated_at']}`",
        f"- Rows: `{len(merged):,}`",
        "- Model/threshold retraining: `No`",
        "- Threshold retuning: `No`",
        "- Private labels opened only after frozen hashes were verified: `Yes`",
        "",
        "## Core blind-test metrics",
        "",
        "| Task | Precision | Recall | F1 | F2 | PR-AUC | FPR | Brier |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in ("anomaly", "shortage_30m", "shortage_60m", "shortage_120m", "data_quality_verification"):
        metric = metrics[name]
        report_lines.append(
            f"| {name} | {format_float(metric.get('precision'))} | "
            f"{format_float(metric.get('recall'))} | {format_float(metric.get('f1'))} | "
            f"{format_float(metric.get('f2'))} | {format_float(metric.get('pr_auc'))} | "
            f"{format_float(metric.get('false_positive_rate'))} | "
            f"{format_float(metric.get('brier_score'))} |"
        )

    report_lines.extend(
        [
            "",
            "## ETA and affected service",
            "",
            f"- ETA MAE: `{format_float(eta_metrics.get('mae_minutes'))}` minutes",
            f"- ETA RMSE: `{format_float(eta_metrics.get('rmse_minutes'))}` minutes",
            f"- ETA within 30 minutes: `{format_float(eta_metrics.get('within_30_minutes_rate'))}`",
            f"- Affected-service accuracy: `{format_float(service_accuracy)}`",
            f"- Anomaly-type accuracy on unusual rows: `{format_float(anomaly_type_accuracy)}`",
            "",
            "## Human review and stakeholder routing",
            "",
            f"- Human-review precision: `{format_float(human_review_metrics.get('precision'))}`",
            f"- Human-review recall: `{format_float(human_review_metrics.get('recall'))}`",
            f"- Primary stakeholder accuracy: `{format_float(primary_route_accuracy)}`",
            f"- Secondary stakeholder accuracy: `{format_float(secondary_route_accuracy)}`",
            f"- Exact route accuracy: `{format_float(exact_route_accuracy)}`",
            "",
            "## Integrity and safety",
            "",
            f"- Frozen hash checks: `{all(hash_match.values())}`",
            f"- Key alignment: `{len(merged):,}/{len(private):,}`",
            f"- Probability/ETA validation: `Passed`",
            f"- Shortage horizon monotonicity violations: `{monotonic_violations}`",
            "- AI final decision maker: `No`",
            "- Automatic money movement/freeze/block/fraud verdict: `Not implemented`",
            "",
            "## Detailed files",
            "",
            "- `phase6c_blind_test_metrics.json`",
            "- `phase6c_context_metrics.csv`",
            "- `phase6c_scenario_anomaly_metrics.csv`",
            "- `phase6c_scenario_shortage60_metrics.csv`",
            "- `phase6c_anomaly_type_metrics.csv`",
            "- `phase6c_service_metrics.csv`",
            "- `phase6c_primary_route_confusion.csv`",
            "",
            "## Honest limitation",
            "",
            "These results are measured on the supplied synthetic blind-test pack. They do not constitute production certification for real MFS operations.",
            "",
        ]
    )
    report_path = report_dir / "PHASE6C_BLIND_EVALUATION_REPORT.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    manifest = {
        "evaluation_id": "phase6c-1.0.0",
        "evaluated_at": evaluation["evaluated_at"],
        "freeze_manifest_sha256": sha256_file(freeze_path),
        "model_bundle_sha256": actual_hashes["model_bundle"],
        "prediction_sha256": actual_hashes["blind_public_predictions"],
        "private_ground_truth_sha256": sha256_file(private_path),
        "metrics_sha256": sha256_file(metrics_path),
        "report_sha256": sha256_file(report_path),
        "retraining_performed": False,
        "threshold_retuning_performed": False,
        "next_step": "Integrate the frozen model bundle into the V2 API runtime and UI without changing Phase 6C metrics.",
    }
    write_json(report_dir / "phase6c_evaluation_manifest.json", manifest)

    print("PHASE 6C FROZEN BLIND EVALUATION PASSED")
    for name in ("anomaly", "shortage_30m", "shortage_60m", "shortage_120m"):
        metric = metrics[name]
        print(
            f"- {name}: precision={metric['precision']:.3f} "
            f"recall={metric['recall']:.3f} f2={metric['f2']:.3f} "
            f"fpr={metric['false_positive_rate']:.3f}"
        )
    print(
        f"- ETA MAE: {format_float(eta_metrics.get('mae_minutes'))} minutes; "
        f"affected-service accuracy: {format_float(service_accuracy)}"
    )
    print(
        f"- primary stakeholder accuracy: {primary_route_accuracy:.3f}; "
        f"exact route accuracy: {exact_route_accuracy:.3f}"
    )
    print(f"- report: {report_path}")
    print("- retraining/retuning performed: NO")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"PHASE 6C EVALUATION FAILED: {exc}", file=sys.stderr)
        raise