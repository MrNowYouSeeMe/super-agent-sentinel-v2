from __future__ import annotations

import json
from math import exp
from pathlib import Path
from typing import Any

from app.domain.ml.models import FeatureContribution, MLFeatureSet, ModelPrediction

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = PROJECT_ROOT / "artifacts" / "models" / "mfs_phase2_baseline.json"


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = exp(-value)
        return 1 / (1 + z)
    z = exp(value)
    return z / (1 + z)


def _load_artifact() -> dict[str, Any]:
    with MODEL_PATH.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def _score(features: dict[str, float], head: dict[str, Any]) -> tuple[float, list[FeatureContribution]]:
    raw = float(head.get("intercept", 0.0))
    contributions: list[FeatureContribution] = []
    weights = head.get("weights", {})
    for feature, weight_raw in weights.items():
        value = float(features.get(feature, 0.0))
        weight = float(weight_raw)
        contribution = value * weight
        raw += contribution
        if abs(contribution) >= 0.08:
            contributions.append(
                FeatureContribution(
                    feature=feature,
                    value=round(value, 6),
                    weight=round(weight, 6),
                    contribution=round(contribution, 6),
                    direction="raises_risk" if contribution > 0 else "lowers_risk",
                )
            )
    contributions.sort(key=lambda item: abs(item.contribution), reverse=True)
    return _sigmoid(raw), contributions[:5]


def _signal_text(features: dict[str, float]) -> list[str]:
    signals: list[str] = []
    if features.get("runway_minutes_capped", 300) <= 60:
        signals.append("Projected runway is within the next 60 minutes.")
    if features.get("cashout_to_in_ratio", 0) >= 3:
        signals.append("Cash-out demand is at least 3x cash-in over the recent window.")
    if features.get("repeated_amount_ratio", 0) >= 0.60:
        signals.append("Repeated-amount concentration is high.")
    if features.get("unique_customer_ratio", 1) <= 0.25:
        signals.append("Activity is concentrated in a small customer group.")
    if features.get("data_quality_score", 1) < 0.50:
        signals.append("Model confidence is capped because source data is unreliable.")
    if not signals:
        signals.append("No high-impact model signal crossed the local baseline threshold.")
    return signals


def _apply_standardization(features: dict[str, float], artifact: dict[str, Any]) -> dict[str, float]:
    standardization = artifact.get("standardization")
    if not standardization:
        return features
    means = standardization.get("means", {})
    stds = standardization.get("stds", {})
    transformed: dict[str, float] = {}
    for name, value in features.items():
        mean = float(means.get(name, 0.0))
        std = float(stds.get(name, 1.0)) or 1.0
        transformed[name] = (value - mean) / std
    return transformed


def predict_resource(feature_set: MLFeatureSet) -> ModelPrediction:
    artifact = _load_artifact()
    scored_features = _apply_standardization(feature_set.features, artifact)
    anomaly_probability, anomaly_contributions = _score(
        scored_features, artifact["anomaly"]
    )
    shortage_probability, shortage_contributions = _score(
        scored_features, artifact["shortage"]
    )
    confidence_adjustment = max(0.20, min(1.0, feature_set.features["data_quality_score"]))
    return ModelPrediction(
        resource_id=feature_set.resource_id,
        model_name=artifact["model_name"],
        model_version=artifact["model_version"],
        model_mode=artifact["model_mode"],
        anomaly_probability=round(anomaly_probability, 6),
        shortage_probability_60m=round(shortage_probability, 6),
        confidence_adjustment=round(confidence_adjustment, 6),
        notable_signals=_signal_text(feature_set.features),
        anomaly_contributions=anomaly_contributions,
        shortage_contributions=shortage_contributions,
    )


def model_metadata() -> dict[str, Any]:
    artifact = _load_artifact()
    return {
        "model_name": artifact["model_name"],
        "model_version": artifact["model_version"],
        "model_mode": artifact["model_mode"],
        "feature_count": len(artifact["feature_names"]),
        "feature_names": artifact["feature_names"],
        "training_status": "baseline_ready_dataset_pending",
        "safety_boundary": "Model output is advisory and cannot move money, freeze accounts, or declare fraud.",
    }


