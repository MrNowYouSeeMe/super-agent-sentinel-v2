from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

FEATURE_COLUMNS = [
    "velocity_vs_baseline",
    "repeated_amount_ratio",
    "unique_customer_ratio",
    "failure_rate",
    "data_quality_score",
    "feed_age_seconds",
    "shared_cash_balance",
    "shared_cash_burn_60m",
    "bkash_balance",
    "bkash_burn_60m",
    "nagad_balance",
    "nagad_burn_60m",
    "rocket_balance",
    "rocket_burn_60m",
]
OPTIONAL_LABELS = [
    "scenario_family",
    "affected_service",
    "is_unusual",
    "shortage_within_60m",
]


def safe_ratio(numerator: float, denominator: float) -> float:
    return max(0.0, float(numerator)) / max(abs(float(denominator)), 1.0)


def row_features(row: pd.Series) -> dict[str, float]:
    return {
        "velocity_vs_baseline": float(row["velocity_vs_baseline"]),
        "repeated_amount_ratio": float(row["repeated_amount_ratio"]),
        "unique_customer_ratio": float(row["unique_customer_ratio"]),
        "failure_rate": float(row["failure_rate"]),
        "data_quality_score": float(row["data_quality_score"]),
        "feed_age_seconds": float(row["feed_age_seconds"]),
        "shared_cash_burn_ratio": safe_ratio(
            row["shared_cash_burn_60m"], row["shared_cash_balance"]
        ),
        "bkash_burn_ratio": safe_ratio(row["bkash_burn_60m"], row["bkash_balance"]),
        "nagad_burn_ratio": safe_ratio(row["nagad_burn_60m"], row["nagad_balance"]),
        "rocket_burn_ratio": safe_ratio(row["rocket_burn_60m"], row["rocket_balance"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    train_path = root / "data" / "raw" / "train" / "pressure_stress_train_5m.csv.gz"
    output_path = root / "artifacts" / "evidence" / "phase9_evidence_index.json"
    if not train_path.exists():
        raise FileNotFoundError(train_path)

    header = pd.read_csv(train_path, compression="gzip", nrows=0)
    available = set(header.columns)
    missing = sorted(set(FEATURE_COLUMNS) - available)
    if missing:
        raise ValueError(f"Training file is missing Phase 9 evidence features: {missing}")

    usecols = FEATURE_COLUMNS + [name for name in OPTIONAL_LABELS if name in available]
    frame = pd.read_csv(train_path, compression="gzip", usecols=usecols)
    frame = frame.replace([np.inf, -np.inf], np.nan).dropna(subset=FEATURE_COLUMNS)

    for label in OPTIONAL_LABELS:
        if label not in frame.columns:
            frame[label] = (
                False
                if label in {"is_unusual", "shortage_within_60m"}
                else "unknown"
            )

    frame["is_unusual"] = frame["is_unusual"].astype(bool)
    frame["shortage_within_60m"] = frame["shortage_within_60m"].astype(bool)
    group_cols = [
        "scenario_family",
        "affected_service",
        "is_unusual",
        "shortage_within_60m",
    ]

    selected: list[pd.DataFrame] = []
    for _, group in frame.groupby(group_cols, dropna=False, sort=True):
        selected.append(group.sample(n=min(4, len(group)), random_state=20260712))

    prototypes_frame = pd.concat(selected, ignore_index=True)
    if len(prototypes_frame) > 320:
        prototypes_frame = prototypes_frame.sample(n=320, random_state=20260712)

    prototypes: list[dict[str, object]] = []
    for index, row in prototypes_frame.reset_index(drop=True).iterrows():
        prototypes.append(
            {
                "prototype_id": f"TRAIN-PROT-{index + 1:04d}",
                "scenario_family": str(row["scenario_family"]),
                "affected_service": str(row["affected_service"]),
                "is_unusual": bool(row["is_unusual"]),
                "shortage_within_60m": bool(row["shortage_within_60m"]),
                "features": row_features(row),
            }
        )

    output = {
        "version": "phase9-evidence-index-1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "training dataset only; no private blind-test labels",
        "source_rows": int(len(frame)),
        "prototype_count": len(prototypes),
        "contains_customer_identifiers": False,
        "contains_transaction_identifiers": False,
        "prototypes": prototypes,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print("PHASE 9 EVIDENCE INDEX BUILT")
    print(f"- source rows: {len(frame):,}")
    print(f"- prototypes: {len(prototypes):,}")
    print(f"- output: {output_path}")
    print("- private blind-test labels opened: NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
