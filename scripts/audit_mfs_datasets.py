from __future__ import annotations

import argparse
import json
import math
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

TARGET_COLUMNS = {
    "is_unusual",
    "anomaly_type",
    "anomaly_family",
    "scenario_family",
    "severity",
    "review_priority",
    "hard_negative_flag",
    "data_quality_issue_flag",
    "liquidity_pressure_flag",
    "label_confidence",
    "combined_edge_case",
    "evidence_codes",
    "shortage_within_30m",
    "shortage_within_60m",
    "shortage_within_120m",
    "actual_time_to_shortage_minutes",
    "affected_service",
    "ground_truth_confidence",
}
FUTURE_PREFIXES = ("future_",)
INTERVENTION_COLUMNS = {
    "approved_cash_support_amount",
    "approved_bkash_support_amount",
    "approved_nagad_support_amount",
    "approved_rocket_support_amount",
}
ID_COLUMNS = {
    "window_id",
    "episode_id",
    "record_id",
    "source_event_id",
    "agent_id",
    "synthetic_outlet_id",
    "synthetic_customer_id",
}
PROVIDERS = {"bkash", "nagad", "rocket"}


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def rate(count: int | float, total: int | float) -> float:
    return round(float(count) / float(total), 8) if total else 0.0


def value_counts_dict(series: pd.Series, top: int | None = None) -> dict[str, int]:
    counts = series.fillna("<missing>").astype(str).value_counts(dropna=False)
    if top is not None:
        counts = counts.head(top)
    return {str(k): int(v) for k, v in counts.items()}


def summarize_csv(path: Path, parse_dates: Iterable[str] = ()) -> dict[str, Any]:
    df = pd.read_csv(path, low_memory=False)
    for col in parse_dates:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return {
        "path": str(path),
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "column_names": list(df.columns),
        "duplicate_rows": int(df.duplicated().sum()),
        "missing_cells": int(df.isna().sum().sum()),
    }


def audit_agents(train_agents_path: Path, test_agents_path: Path) -> dict[str, Any]:
    train = pd.read_csv(train_agents_path)
    test = pd.read_csv(test_agents_path)
    train_ids = set(train["agent_id"].astype(str))
    test_ids = set(test["agent_id"].astype(str))
    unseen = sorted(test_ids - train_ids)
    seen = sorted(test_ids & train_ids)
    affinity_cols = [f"provider_affinity_{p}" for p in sorted(PROVIDERS)]
    affinity_error = None
    if all(c in train.columns for c in affinity_cols):
        sums = train[affinity_cols].sum(axis=1)
        affinity_error = float((sums - 1.0).abs().max())
    return {
        "train_agents": int(len(train)),
        "test_agents": int(len(test)),
        "seen_test_agents": int(len(seen)),
        "unseen_test_agents": int(len(unseen)),
        "unseen_fraction": rate(len(unseen), len(test)),
        "train_area_count": int(train["area_id"].nunique()),
        "test_area_count": int(test["area_id"].nunique()),
        "train_location_types": value_counts_dict(train["location_type"]),
        "train_activity_segments": value_counts_dict(train["activity_segment"]),
        "test_new_agent_flag": value_counts_dict(test.get("is_new_test_agent", pd.Series(dtype=int))),
        "max_provider_affinity_sum_error": None if affinity_error is None else round(affinity_error, 10),
        "duplicate_train_agent_ids": int(train["agent_id"].duplicated().sum()),
        "duplicate_test_agent_ids": int(test["agent_id"].duplicated().sum()),
    }


def audit_full_agent_pickles(agent_dir: Path) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    files = sorted(agent_dir.glob("*.pkl.xz"))
    total_rows = 0
    split_counts: Counter[str] = Counter()
    unusual_counts: Counter[str] = Counter()
    shortage_counts: dict[str, Counter[str]] = {
        "shortage_within_30m": Counter(),
        "shortage_within_60m": Counter(),
        "shortage_within_120m": Counter(),
    }
    anomaly_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    severity_counts: Counter[str] = Counter()
    affected_counts: Counter[str] = Counter()
    hard_negative_counts: Counter[str] = Counter()
    dqi_counts: Counter[str] = Counter()
    combined_counts: Counter[str] = Counter()
    missing_counts: Counter[str] = Counter()
    non_null_counts: Counter[str] = Counter()
    schemas: Counter[tuple[str, ...]] = Counter()
    agent_rows: list[dict[str, Any]] = []
    duplicate_window_ids = 0
    min_time: pd.Timestamp | None = None
    max_time: pd.Timestamp | None = None
    invalid_ratio_counts: Counter[str] = Counter()
    negative_balance_counts: Counter[str] = Counter()

    for index, file in enumerate(files, start=1):
        df = pd.read_pickle(file, compression="xz")
        total_rows += len(df)
        schemas[tuple(df.columns)] += 1
        if "window_end" in df.columns:
            times = pd.to_datetime(df["window_end"], errors="coerce")
            if times.notna().any():
                local_min = times.min()
                local_max = times.max()
                min_time = local_min if min_time is None or local_min < min_time else min_time
                max_time = local_max if max_time is None or local_max > max_time else max_time
        duplicate_window_ids += int(df["window_id"].duplicated().sum()) if "window_id" in df else 0
        for col in df.columns:
            missing_counts[col] += int(df[col].isna().sum())
            non_null_counts[col] += int(df[col].notna().sum())
        for key, counter in [
            ("split", split_counts),
            ("is_unusual", unusual_counts),
            ("anomaly_type", anomaly_counts),
            ("anomaly_family", family_counts),
            ("severity", severity_counts),
            ("affected_service", affected_counts),
            ("hard_negative_flag", hard_negative_counts),
            ("data_quality_issue_flag", dqi_counts),
            ("combined_edge_case", combined_counts),
        ]:
            if key in df.columns:
                counter.update(df[key].fillna("<missing>").astype(str).value_counts().to_dict())
        for target, counter in shortage_counts.items():
            if target in df.columns:
                counter.update(df[target].fillna("<missing>").astype(str).value_counts().to_dict())

        for col in ["failure_rate", "repeated_amount_ratio", "unique_customer_ratio", "reversal_rate", "missing_record_ratio", "duplicate_source_ratio", "out_of_order_ratio", "data_quality_score", "label_confidence", "ground_truth_confidence"]:
            if col in df.columns:
                numeric = pd.to_numeric(df[col], errors="coerce")
                invalid_ratio_counts[col] += int(((numeric < 0) | (numeric > 1)).sum())
        for col in ["shared_cash_balance", "bkash_reported_e_money_balance", "nagad_reported_e_money_balance", "rocket_reported_e_money_balance"]:
            if col in df.columns:
                numeric = pd.to_numeric(df[col], errors="coerce")
                negative_balance_counts[col] += int((numeric < 0).sum())

        agent_rows.append({
            "file": file.name,
            "rows": int(len(df)),
            "columns": int(len(df.columns)),
            "min_window_end": None if "window_end" not in df or df["window_end"].isna().all() else str(pd.to_datetime(df["window_end"], errors="coerce").min()),
            "max_window_end": None if "window_end" not in df or df["window_end"].isna().all() else str(pd.to_datetime(df["window_end"], errors="coerce").max()),
            "unusual_rows": int(pd.to_numeric(df.get("is_unusual", 0), errors="coerce").fillna(0).sum()) if "is_unusual" in df else 0,
            "shortage_60m_rows": int(pd.to_numeric(df.get("shortage_within_60m", 0), errors="coerce").fillna(0).sum()) if "shortage_within_60m" in df else 0,
            "duplicate_window_ids": int(df["window_id"].duplicated().sum()) if "window_id" in df else 0,
        })
        if index % 8 == 0 or index == len(files):
            print(f"  audited {index}/{len(files)} agent pickles", flush=True)

    missing_rows = []
    for col in sorted(missing_counts):
        denominator = missing_counts[col] + non_null_counts[col]
        missing_rows.append({
            "column": col,
            "missing_count": int(missing_counts[col]),
            "total_count": int(denominator),
            "missing_rate": rate(missing_counts[col], denominator),
        })

    summary = {
        "files": int(len(files)),
        "rows": int(total_rows),
        "date_min": None if min_time is None else min_time.isoformat(),
        "date_max": None if max_time is None else max_time.isoformat(),
        "schema_variants": int(len(schemas)),
        "schema_file_counts": {str(i + 1): int(count) for i, count in enumerate(schemas.values())},
        "split_counts": dict(split_counts),
        "is_unusual_counts": dict(unusual_counts),
        "unusual_positive_rate": rate(unusual_counts.get("1", 0), total_rows),
        "shortage_counts": {k: dict(v) for k, v in shortage_counts.items()},
        "shortage_60m_positive_rate": rate(shortage_counts["shortage_within_60m"].get("1", 0), total_rows),
        "top_anomaly_types": dict(anomaly_counts.most_common(30)),
        "anomaly_family_counts": dict(family_counts),
        "severity_counts": dict(severity_counts),
        "affected_service_counts": dict(affected_counts),
        "hard_negative_counts": dict(hard_negative_counts),
        "data_quality_issue_counts": dict(dqi_counts),
        "top_combined_edge_cases": dict(combined_counts.most_common(20)),
        "duplicate_window_ids_within_agent_files": int(duplicate_window_ids),
        "invalid_ratio_counts": dict(invalid_ratio_counts),
        "negative_balance_counts": dict(negative_balance_counts),
    }
    return summary, pd.DataFrame(agent_rows), pd.DataFrame(missing_rows)


def audit_model_ready(train_path: Path, test_path: Path) -> dict[str, Any]:
    train = pd.read_csv(train_path, low_memory=False)
    test = pd.read_csv(test_path, low_memory=False)
    train_cols = list(train.columns)
    test_cols = list(test.columns)
    label_and_future = [c for c in train_cols if c in TARGET_COLUMNS or c.startswith(FUTURE_PREFIXES)]
    train_only = [c for c in train_cols if c not in test_cols]
    test_only = [c for c in test_cols if c not in train_cols]
    unexpected_train_only = sorted(set(train_only) - set(label_and_future))
    unexpected_test_only = sorted(test_only)
    feature_candidates = [
        c for c in test_cols
        if c not in ID_COLUMNS
        and c not in {"split", "window_end"}
        and c not in INTERVENTION_COLUMNS
    ]
    categorical_candidates = [c for c in feature_candidates if test[c].dtype == "object"]
    numeric_candidates = [c for c in feature_candidates if c not in categorical_candidates]
    suspicious_feature_columns = [
        c for c in test_cols
        if c.startswith("approved_") or "future" in c.lower() or "ground_truth" in c.lower()
    ]
    return {
        "train_sample_rows": int(len(train)),
        "test_sample_rows": int(len(test)),
        "train_columns": int(len(train_cols)),
        "test_columns": int(len(test_cols)),
        "train_only_columns": train_only,
        "test_only_columns": test_only,
        "unexpected_train_only_columns": unexpected_train_only,
        "unexpected_test_only_columns": unexpected_test_only,
        "public_test_is_feature_subset": set(test_cols).issubset(set(train_cols)),
        "target_and_future_columns_removed_from_public_test": all(c not in test_cols for c in label_and_future),
        "feature_candidate_count": int(len(feature_candidates)),
        "numeric_feature_candidate_count": int(len(numeric_candidates)),
        "categorical_feature_candidate_count": int(len(categorical_candidates)),
        "categorical_feature_candidates": categorical_candidates,
        "intervention_columns_to_exclude_from_predictive_features": sorted(c for c in test_cols if c in INTERVENTION_COLUMNS),
        "suspicious_public_feature_columns": suspicious_feature_columns,
        "train_window_duplicates": int(train["window_id"].duplicated().sum()) if "window_id" in train else 0,
        "test_window_duplicates": int(test["window_id"].duplicated().sum()) if "window_id" in test else 0,
        "train_sample_unusual_rate": rate(pd.to_numeric(train.get("is_unusual", 0), errors="coerce").fillna(0).sum(), len(train)),
        "train_sample_shortage_60m_rate": rate(pd.to_numeric(train.get("shortage_within_60m", 0), errors="coerce").fillna(0).sum(), len(train)),
    }


def audit_stress(train_path: Path, test_public_path: Path, private_labels_path: Path) -> dict[str, Any]:
    train = pd.read_csv(train_path, low_memory=False)
    public = pd.read_csv(test_public_path, low_memory=False)
    # Strict blind policy: read only header + alignment keys from private labels.
    private_header = list(pd.read_csv(private_labels_path, nrows=0).columns)
    private_keys = pd.read_csv(private_labels_path, usecols=["episode_id", "window_id", "timestamp"], low_memory=False)
    public_keys = public[["episode_id", "window_id", "timestamp"]]
    key_alignment = public_keys.equals(private_keys)
    train_feature_cols = [c for c in train.columns if c not in TARGET_COLUMNS and not c.startswith(FUTURE_PREFIXES)]
    public_cols = list(public.columns)
    return {
        "train_rows": int(len(train)),
        "train_episodes": int(train["episode_id"].nunique()),
        "test_public_rows": int(len(public)),
        "test_public_episodes": int(public["episode_id"].nunique()),
        "private_rows_key_only": int(len(private_keys)),
        "public_private_key_alignment": bool(key_alignment),
        "private_label_values_inspected": False,
        "private_header_columns": private_header,
        "train_is_unusual_counts": value_counts_dict(train["is_unusual"]),
        "train_unusual_rate": rate(pd.to_numeric(train["is_unusual"], errors="coerce").fillna(0).sum(), len(train)),
        "train_shortage_60m_counts": value_counts_dict(train["shortage_within_60m"]),
        "train_shortage_60m_rate": rate(pd.to_numeric(train["shortage_within_60m"], errors="coerce").fillna(0).sum(), len(train)),
        "train_hard_negative_counts": value_counts_dict(train["hard_negative_flag"]),
        "train_data_quality_issue_counts": value_counts_dict(train["data_quality_issue_flag"]),
        "top_train_scenario_families": value_counts_dict(train["scenario_family"], top=20),
        "top_train_anomaly_types": value_counts_dict(train["anomaly_type"], top=30),
        "affected_service_counts": value_counts_dict(train["affected_service"], top=10),
        "feature_columns_match_public_test": set(public_cols).issubset(set(train_feature_cols)),
        "public_test_extra_columns": sorted(set(public_cols) - set(train_feature_cols)),
        "train_feature_columns_missing_from_public": sorted(set(train_feature_cols) - set(public_cols)),
        "duplicate_train_window_ids": int(train["window_id"].duplicated().sum()),
        "duplicate_public_window_ids": int(public["window_id"].duplicated().sum()),
    }


def audit_transactions(train_path: Path, test_path: Path) -> dict[str, Any]:
    def one(path: Path) -> dict[str, Any]:
        df = pd.read_csv(path, low_memory=False)
        amount = pd.to_numeric(df["amount_bdt"], errors="coerce")
        events = pd.to_datetime(df["event_timestamp"], errors="coerce")
        ingested = pd.to_datetime(df["ingestion_timestamp"], errors="coerce")
        delay = (ingested - events).dt.total_seconds()
        return {
            "rows": int(len(df)),
            "providers": value_counts_dict(df["provider_id"]),
            "transaction_types": value_counts_dict(df["transaction_type"]),
            "statuses": value_counts_dict(df["transaction_status"]),
            "channels": value_counts_dict(df["channel"]),
            "duplicate_record_ids": int(df["record_id"].duplicated().sum()),
            "duplicate_source_event_ids": int(df["source_event_id"].duplicated().sum()),
            "negative_amounts": int((amount < 0).sum()),
            "zero_amounts": int((amount == 0).sum()),
            "amount_p50": float(amount.quantile(0.50)),
            "amount_p95": float(amount.quantile(0.95)),
            "amount_p99": float(amount.quantile(0.99)),
            "amount_max": float(amount.max()),
            "negative_ingestion_delay_rows": int((delay < 0).sum()),
            "timestamp_quality": value_counts_dict(df["timestamp_quality"]),
        }
    return {"train_sample": one(train_path), "test_sample": one(test_path)}


def infer_gaps(full_summary: dict[str, Any], stress_summary: dict[str, Any], model_summary: dict[str, Any]) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    unusual_rate = float(full_summary.get("unusual_positive_rate", 0))
    if unusual_rate < 0.02:
        gaps.append({
            "gap": "Extreme anomaly class imbalance in full historical windows",
            "severity": "high",
            "action": "Use class/sample weighting, episode-aware sampling, hard-negative batches, PR-AUC, and threshold tuning. Do not use accuracy as the main metric.",
        })
    gaps.append({
        "gap": "Human stakeholder routing is not a model target",
        "severity": "intentional",
        "action": "Keep routing deterministic from classification, affected service, severity, confidence, area, and authorization scope. AI must not choose final authority.",
    })
    gaps.append({
        "gap": "No confirmed-fraud target",
        "severity": "intentional",
        "action": "Use is_unusual as review-required, never as fraud confirmation. Preserve human review and safe language.",
    })
    gaps.append({
        "gap": "Provider-specific shortage booleans are not explicit for every provider",
        "severity": "medium",
        "action": "Derive provider-specific 30/60/120-minute targets from future provider balances and provider critical thresholds, while keeping affected_service as a separate evaluation label.",
    })
    gaps.append({
        "gap": "Approved support amounts are post-decision/intervention fields",
        "severity": "high",
        "action": "Exclude approved_*_support_amount from predictive features to avoid policy/intervention leakage; retain only for workflow/audit analysis.",
    })
    gaps.append({
        "gap": "Synthetic-to-real generalization is unproven",
        "severity": "high",
        "action": "State this limitation, evaluate unseen agents and distribution shifts, calibrate confidence, and never claim production fraud detection.",
    })
    return gaps


def build_plan(audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "principles": [
            "AI produces scores/evidence, not final financial decisions.",
            "Input validation and output validation wrap every model.",
            "Data-quality state controls confidence and routing.",
            "Private blind-test labels remain untouched until all models, features, thresholds, and fusion rules are frozen.",
            "Provider boundaries are preserved in features, outputs, and stakeholder visibility.",
        ],
        "model_tasks": [
            {
                "task": "Anomaly review classifier",
                "target": "is_unusual",
                "preferred_fast_models": ["LightGBM/CatBoost if available", "HistGradientBoosting fallback", "logistic rule baseline"],
                "special_handling": ["class weights", "hard-negative sampling", "label_confidence sample weights", "group/time validation"],
                "metrics": ["precision", "recall", "F1", "PR-AUC", "hard-negative FPR"],
            },
            {
                "task": "Shortage classifiers",
                "target": "shortage_within_30m, shortage_within_60m, shortage_within_120m",
                "preferred_fast_models": ["LightGBM/CatBoost", "HistGradientBoosting fallback"],
                "metrics": ["precision", "recall", "F1", "PR-AUC", "Brier score", "calibration"],
            },
            {
                "task": "Runway regression",
                "target": "actual_time_to_shortage_minutes on positive/finite rows",
                "preferred_fast_models": ["gradient boosting regressor", "quantile models for ETA interval"],
                "metrics": ["MAE", "median absolute error", "interval coverage"],
            },
            {
                "task": "Affected resource selection",
                "target": "derived provider-specific shortage flags + affected_service evaluation",
                "preferred_fast_models": ["separate per-resource models", "deterministic argmax/rule fusion"],
                "metrics": ["macro F1", "provider-wise recall", "shared-cash vs provider confusion"],
            },
            {
                "task": "Data-quality gate",
                "target": "not learned as final decision",
                "preferred_fast_models": ["deterministic validation/rules"],
                "metrics": ["stale/conflict detection coverage", "safe-degradation rate"],
            },
        ],
        "feature_policy": {
            "include": [
                "current/past operational features",
                "provider-specific balances and burns",
                "shared-cash balance and burns",
                "transaction velocity/concentration/failure features",
                "context flags and agent profile",
                "feed/reconciliation/data-quality features",
            ],
            "exclude": [
                "future_* columns",
                "target/ground-truth columns",
                "review_priority/severity/evidence_codes when predicting risk",
                "approved_*_support_amount intervention columns",
                "raw IDs as unconstrained numeric features",
            ],
        },
        "validation_split": [
            "Use provided 2024-2025 train/validation split for development.",
            "Add group checks by agent and peer group to measure memorization.",
            "Use 2026-H1 public features only for frozen blind predictions.",
            "Use private labels once for final evaluation after freeze.",
        ],
        "speed_strategy": [
            "Train on compact 5-minute feature tables, not raw transaction events.",
            "Use column pruning and compact dtypes.",
            "Use episode-aware weighted sampling for rapid experiments, then final full-data fit.",
            "Train independent task heads/models in parallel where practical.",
            "Serialize lightweight CPU artifacts and precompute categorical encodings.",
            "Call OpenAI only for review-worthy explanation, never per row or for scoring.",
        ],
        "synthetic_gap_policy": [
            "Only add synthetic rows when a scenario/provider/context is demonstrably underrepresented.",
            "Tag every augmented row with augmentation_source and scenario_source.",
            "Generate augmentation from train assumptions only; never use blind private labels.",
            "Keep original and augmented metrics separate.",
            "Prefer derived features before generating more rows.",
        ],
        "stakeholder_routing": [
            "Provider liquidity -> area manager + affected provider operations.",
            "Shared-cash pressure -> area manager + outlet operator.",
            "Unusual activity -> risk/compliance reviewer.",
            "Liquidity + anomaly -> joint area manager and risk review.",
            "Stale/conflicting feed -> data/provider operations before escalation.",
            "High-severity cross-area pattern -> central operations/management.",
        ],
    }


def write_markdown(audit: dict[str, Any], path: Path) -> None:
    full = audit["training_full_history"]
    stress = audit["stress_benchmark"]
    model = audit["model_ready_samples"]
    agents = audit["agents"]
    lines = [
        "# MFS Dataset Audit Report",
        "",
        f"Generated: {audit['generated_at']}",
        "",
        "## Blind-test policy",
        "",
        "Private test label values were not inspected. Only header and key alignment were checked.",
        "",
        "## Core inventory",
        "",
        f"- Full historical agent files: **{full['files']}**",
        f"- Full historical rows: **{full['rows']:,}**",
        f"- Train agents: **{agents['train_agents']}**",
        f"- Blind-test agents: **{agents['test_agents']}**",
        f"- Blind-test unseen agents: **{agents['unseen_test_agents']} ({agents['unseen_fraction']:.1%})**",
        f"- Exact 5-minute stress train rows: **{stress['train_rows']:,}**",
        f"- Exact 5-minute stress public-test rows: **{stress['test_public_rows']:,}**",
        "",
        "## Main label balance",
        "",
        f"- Full-history unusual positive rate: **{full['unusual_positive_rate']:.4%}**",
        f"- Full-history shortage-within-60m rate: **{full['shortage_60m_positive_rate']:.4%}**",
        f"- Stress-train unusual positive rate: **{stress['train_unusual_rate']:.4%}**",
        f"- Stress-train shortage-within-60m rate: **{stress['train_shortage_60m_rate']:.4%}**",
        "",
        "The full historical anomaly target is extremely imbalanced, so accuracy is not an acceptable primary metric.",
        "",
        "## Leakage controls",
        "",
        f"- Public model-ready test is a feature subset of train: **{model['public_test_is_feature_subset']}**",
        f"- Future/target columns removed from public test: **{model['target_and_future_columns_removed_from_public_test']}**",
        f"- Intervention columns excluded by policy: **{', '.join(model['intervention_columns_to_exclude_from_predictive_features']) or 'none found'}**",
        "",
        "## Important gaps and decisions",
        "",
    ]
    for item in audit["gaps"]:
        lines.append(f"- **{item['gap']}** ({item['severity']}): {item['action']}")
    lines.extend([
        "",
        "## Final modeling direction",
        "",
        "- Separate fast models for anomaly, 30/60/120-minute shortage, and runway regression.",
        "- Data-quality handling stays deterministic and reduces confidence.",
        "- Provider-specific predictions are fused with transparent rules.",
        "- Stakeholder routing remains deterministic and authorization-scoped.",
        "- AI never declares fraud or performs financial action.",
        "",
        "## Generated files",
        "",
        "- `audit_summary.json`",
        "- `agent_file_summary.csv`",
        "- `full_history_missingness.csv`",
        "- `model_training_plan.json`",
        "- `training_feature_contract.json`",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.project_root.resolve()
    train = root / "data" / "raw" / "train"
    test_public = root / "data" / "raw" / "blind_test" / "public"
    private = root / "data" / "private" / "blind_test_ground_truth"
    out = root / "reports" / "dataset_audit"
    out.mkdir(parents=True, exist_ok=True)

    required = [
        train / "agents.csv",
        train / "providers.csv",
        train / "agent_pickles",
        train / "model_ready_train_sample_50000.csv.gz",
        train / "transaction_event_sample_2024_2025.csv.gz",
        train / "pressure_stress_train_5m.csv.gz",
        test_public / "agents_test.csv",
        test_public / "model_ready_test_sample_20000.csv.gz",
        test_public / "transaction_event_sample_2026H1.csv.gz",
        test_public / "pressure_stress_test_5m.csv.gz",
        private / "pressure_stress_labels_private.csv.gz",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError("Missing required dataset paths:\n" + "\n".join(missing))

    print("Auditing agent metadata...", flush=True)
    agents = audit_agents(train / "agents.csv", test_public / "agents_test.csv")

    print("Auditing full 2-year agent pickles (streamed one file at a time)...", flush=True)
    full_summary, agent_df, missing_df = audit_full_agent_pickles(train / "agent_pickles")

    print("Auditing model-ready train/public-test schemas...", flush=True)
    model_ready = audit_model_ready(
        train / "model_ready_train_sample_50000.csv.gz",
        test_public / "model_ready_test_sample_20000.csv.gz",
    )

    print("Auditing exact 5-minute stress benchmark with blind-label guard...", flush=True)
    stress = audit_stress(
        train / "pressure_stress_train_5m.csv.gz",
        test_public / "pressure_stress_test_5m.csv.gz",
        private / "pressure_stress_labels_private.csv.gz",
    )

    print("Auditing transaction-event samples...", flush=True)
    transactions = audit_transactions(
        train / "transaction_event_sample_2024_2025.csv.gz",
        test_public / "transaction_event_sample_2026H1.csv.gz",
    )

    providers = pd.read_csv(train / "providers.csv")
    contexts = pd.read_csv(train / "contextual_events.csv")
    scenarios = pd.read_csv(train / "scenario_catalog.csv")
    provider_ids = set(providers["provider_id"].astype(str))

    audit: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "audit_version": "6A.1",
        "blind_test_policy": {
            "private_label_values_inspected": False,
            "private_use": "header and key alignment only until model/threshold/fusion freeze",
        },
        "agents": agents,
        "provider_metadata": {
            "provider_ids": sorted(provider_ids),
            "provider_separation_valid": provider_ids == PROVIDERS,
            "warning_thresholds": dict(zip(providers["provider_id"].astype(str), providers["warning_threshold"].astype(float))),
            "critical_thresholds": dict(zip(providers["provider_id"].astype(str), providers["critical_threshold"].astype(float))),
        },
        "context_coverage": {
            "rows": int(len(contexts)),
            "event_types": sorted(contexts["event_type"].astype(str).unique().tolist()),
            "scenario_family_counts": value_counts_dict(scenarios["family"]),
            "scenario_count": int(len(scenarios)),
        },
        "training_full_history": full_summary,
        "model_ready_samples": model_ready,
        "stress_benchmark": stress,
        "transaction_samples": transactions,
    }
    audit["gaps"] = infer_gaps(full_summary, stress, model_ready)
    plan = build_plan(audit)

    feature_contract = {
        "version": "6A.1",
        "feature_source": "public-test-compatible columns",
        "feature_candidates": [
            c for c in pd.read_csv(test_public / "model_ready_test_sample_20000.csv.gz", nrows=0).columns
            if c not in ID_COLUMNS and c not in {"split", "window_end"} and c not in INTERVENTION_COLUMNS
        ],
        "categorical_features": model_ready["categorical_feature_candidates"],
        "excluded_intervention_columns": model_ready["intervention_columns_to_exclude_from_predictive_features"],
        "prohibited_leakage_columns": sorted(TARGET_COLUMNS) + ["future_*"],
        "targets": [
            "is_unusual",
            "shortage_within_30m",
            "shortage_within_60m",
            "shortage_within_120m",
            "actual_time_to_shortage_minutes",
            "derived_provider_specific_shortage_targets",
        ],
        "output_validation": [
            "all probabilities clipped/validated to [0,1]",
            "affected resource must be shared_cash/bkash/nagad/rocket",
            "confidence reduced for degraded/unreliable data",
            "medium/high cases require human review",
            "no fraud verdict or automated financial action",
        ],
    }

    (out / "audit_summary.json").write_text(json.dumps(json_safe(audit), indent=2), encoding="utf-8")
    (out / "model_training_plan.json").write_text(json.dumps(json_safe(plan), indent=2), encoding="utf-8")
    (out / "training_feature_contract.json").write_text(json.dumps(json_safe(feature_contract), indent=2), encoding="utf-8")
    agent_df.to_csv(out / "agent_file_summary.csv", index=False)
    missing_df.sort_values(["missing_rate", "column"], ascending=[False, True]).to_csv(out / "full_history_missingness.csv", index=False)
    write_markdown(audit, out / "AUDIT_REPORT.md")

    print("DATASET AUDIT PASSED", flush=True)
    print(f"- report: {out / 'AUDIT_REPORT.md'}", flush=True)
    print(f"- summary: {out / 'audit_summary.json'}", flush=True)
    print(f"- plan: {out / 'model_training_plan.json'}", flush=True)
    print(f"- full historical rows: {full_summary['rows']:,}", flush=True)
    print(f"- unusual positive rate: {full_summary['unusual_positive_rate']:.4%}", flush=True)
    print(f"- stress public/private keys aligned: {stress['public_private_key_alignment']}", flush=True)


if __name__ == "__main__":
    main()