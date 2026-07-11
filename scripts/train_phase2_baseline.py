"""Train a small pure-Python logistic baseline for SuperAgent Sentinel V2.

This script is intentionally lightweight so it can run locally on Windows without
heavy ML dependencies. It expects a CSV with the feature columns generated from
the user's MFS dataset and optional labels:

Required label columns for supervised training:
- is_unusual
- shortage_within_60m

If labels are missing, the script validates the dataset and exits with a clear
message. The current checked-in artifact remains a deterministic baseline until
real dataset training is run.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

FEATURE_NAMES = [
    "balance_to_buffer_ratio",
    "net_burn_per_minute",
    "runway_minutes_capped",
    "cashout_to_in_ratio",
    "transaction_count_5m",
    "repeated_amount_ratio",
    "unique_customer_ratio",
    "failure_rate",
    "feed_age_minutes",
    "reconciliation_ratio",
    "completeness_ratio",
    "source_quality_score",
    "data_quality_score",
    "festival_or_market_day",
    "is_shared_cash",
]


def sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1 / (1 + z)
    z = math.exp(value)
    return z / (1 + z)


def read_rows(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [name for name in FEATURE_NAMES if name not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(f"Missing required feature columns: {', '.join(missing)}")
        if "is_unusual" not in (reader.fieldnames or []) or "shortage_within_60m" not in (reader.fieldnames or []):
            raise SystemExit("CSV must include labels: is_unusual and shortage_within_60m")
        for raw in reader:
            row: dict[str, float] = {}
            for name in FEATURE_NAMES + ["is_unusual", "shortage_within_60m"]:
                row[name] = float(raw.get(name) or 0.0)
            rows.append(row)
    if not rows:
        raise SystemExit("No training rows found.")
    return rows


def standardize(rows: list[dict[str, float]]) -> tuple[list[dict[str, float]], dict[str, float], dict[str, float]]:
    means: dict[str, float] = {}
    stds: dict[str, float] = {}
    for name in FEATURE_NAMES:
        values = [row[name] for row in rows]
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / max(len(values), 1)
        std = math.sqrt(variance) or 1.0
        means[name] = mean
        stds[name] = std
    transformed: list[dict[str, float]] = []
    for row in rows:
        item = row.copy()
        for name in FEATURE_NAMES:
            item[name] = (row[name] - means[name]) / stds[name]
        transformed.append(item)
    return transformed, means, stds


def train_head(rows: list[dict[str, float]], label: str, epochs: int, lr: float) -> tuple[float, dict[str, float]]:
    weights = {name: 0.0 for name in FEATURE_NAMES}
    bias = 0.0
    positive = sum(1 for row in rows if row[label] >= 0.5)
    negative = len(rows) - positive
    positive_weight = negative / max(positive, 1)

    for _ in range(epochs):
        grad_b = 0.0
        grad_w = {name: 0.0 for name in FEATURE_NAMES}
        for row in rows:
            logit = bias + sum(weights[name] * row[name] for name in FEATURE_NAMES)
            pred = sigmoid(logit)
            target = 1.0 if row[label] >= 0.5 else 0.0
            sample_weight = positive_weight if target > 0 else 1.0
            error = (pred - target) * sample_weight
            grad_b += error
            for name in FEATURE_NAMES:
                grad_w[name] += error * row[name]
        scale = 1 / len(rows)
        bias -= lr * grad_b * scale
        for name in FEATURE_NAMES:
            weights[name] -= lr * grad_w[name] * scale
    return bias, weights


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/models/mfs_phase2_trained.json"))
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--lr", type=float, default=0.08)
    args = parser.parse_args()

    rows = read_rows(args.csv_path)
    transformed, means, stds = standardize(rows)
    anomaly_bias, anomaly_weights = train_head(transformed, "is_unusual", args.epochs, args.lr)
    shortage_bias, shortage_weights = train_head(transformed, "shortage_within_60m", args.epochs, args.lr)

    artifact = {
        "model_name": "mfs_phase2_dataset_logistic",
        "model_version": "2.1.0-trained-local",
        "model_mode": "trained_logistic_artifact",
        "feature_names": FEATURE_NAMES,
        "standardization": {"means": means, "stds": stds},
        "anomaly": {"intercept": anomaly_bias, "weights": anomaly_weights},
        "shortage": {"intercept": shortage_bias, "weights": shortage_weights},
        "training_rows": len(rows),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(f"Wrote trained artifact: {args.output}")


if __name__ == "__main__":
    main()

